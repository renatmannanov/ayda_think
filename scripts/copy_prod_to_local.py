"""
Copy fragment data from production PostgreSQL to local PostgreSQL.
Usage: python scripts/copy_prod_to_local.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from psycopg2.extras import Json
from sqlalchemy import create_engine, text

PROD_URL = os.getenv("DATABASE_PUBLIC_URL_VECTOR")
LOCAL_URL = "postgresql://postgres:localpass@localhost:5433/ayda_think"

if not PROD_URL:
    print("ERROR: DATABASE_PUBLIC_URL_VECTOR not set in .env")
    sys.exit(1)


def copy_data():
    prod_engine = create_engine(PROD_URL)
    local_engine = create_engine(LOCAL_URL)

    # Init pgvector on local
    with local_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        print("pgvector extension enabled")

    # Copy fragments table
    with prod_engine.connect() as prod_conn:
        # Get table schema info
        rows = prod_conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'fragments' ORDER BY ordinal_position"
        )).fetchall()
        print(f"Fragments columns: {[r[0] for r in rows]}")

        # Count
        count = prod_conn.execute(text("SELECT COUNT(*) FROM fragments")).scalar()
        print(f"Production fragments: {count}")

        # Read all fragments
        fragments = prod_conn.execute(text("SELECT * FROM fragments")).fetchall()
        col_names = [r[0] for r in rows]

    # Create table on local
    with local_engine.connect() as local_conn:
        # Drop and recreate
        local_conn.execute(text("DROP TABLE IF EXISTS fragment_clusters CASCADE"))
        local_conn.execute(text("DROP TABLE IF EXISTS clusters CASCADE"))
        local_conn.execute(text("DROP TABLE IF EXISTS fragments CASCADE"))

        # Create fragments table matching prod schema
        local_conn.execute(text("""
            CREATE TABLE fragments (
                id SERIAL PRIMARY KEY,
                external_id VARCHAR(255) UNIQUE,
                source VARCHAR(50) NOT NULL,
                text TEXT NOT NULL,
                embedding vector(1536),
                tags TEXT[] DEFAULT '{}',
                created_at TIMESTAMP NOT NULL,
                indexed_at TIMESTAMP DEFAULT NOW(),
                metadata JSONB DEFAULT '{}',
                content_type VARCHAR(20) DEFAULT 'note',
                language VARCHAR(5),
                is_duplicate BOOLEAN DEFAULT FALSE,
                is_outdated BOOLEAN DEFAULT FALSE
            )
        """))

        local_conn.execute(text("""
            CREATE TABLE clusters (
                id SERIAL PRIMARY KEY,
                version INTEGER NOT NULL,
                label INTEGER NOT NULL,
                size INTEGER DEFAULT 0,
                preview TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(version, label)
            )
        """))

        local_conn.execute(text("""
            CREATE TABLE fragment_clusters (
                fragment_id INTEGER REFERENCES fragments(id),
                cluster_id INTEGER REFERENCES clusters(id),
                version INTEGER NOT NULL,
                PRIMARY KEY (fragment_id, version)
            )
        """))

        # HNSW index
        local_conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_fragments_embedding "
            "ON fragments USING hnsw (embedding vector_cosine_ops)"
        ))

        local_conn.commit()
        print("Tables created")

        # Insert fragments in batches
        batch_size = 100
        inserted = 0
        for i in range(0, len(fragments), batch_size):
            batch = fragments[i:i + batch_size]
            for row in batch:
                row_dict = dict(zip(col_names, row))
                # Convert dict fields to Json for psycopg2
                if 'metadata' in row_dict and isinstance(row_dict['metadata'], dict):
                    row_dict['metadata'] = Json(row_dict['metadata'])
                # Build parameterized insert
                cols = [c for c in col_names if c in row_dict]
                placeholders = [f":{c}" for c in cols]
                sql = f"INSERT INTO fragments ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) ON CONFLICT (id) DO NOTHING"
                local_conn.execute(text(sql), row_dict)
            local_conn.commit()
            inserted += len(batch)
            print(f"  Inserted {inserted}/{len(fragments)}")

        # Reset sequence
        local_conn.execute(text("SELECT setval('fragments_id_seq', (SELECT MAX(id) FROM fragments))"))
        local_conn.commit()

        final_count = local_conn.execute(text("SELECT COUNT(*) FROM fragments")).scalar()
        embedded = local_conn.execute(text("SELECT COUNT(*) FROM fragments WHERE embedding IS NOT NULL")).scalar()
        print(f"\nDone! Local DB: {final_count} fragments, {embedded} with embeddings")


if __name__ == "__main__":
    copy_data()
