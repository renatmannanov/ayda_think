"""
Test /artifact synthesis locally without running the bot.
Usage: python scripts/test_synthesis.py "тема для анализа"
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DATABASE_URL BEFORE any project imports
os.environ["DATABASE_URL"] = "postgresql://postgres:localpass@localhost:5433/ayda_think"

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Patch db module BEFORE init_db
import storage.db as db_mod
from sqlalchemy import create_engine
LOCAL_URL = os.environ["DATABASE_URL"]
db_mod.DATABASE_URL = LOCAL_URL
db_mod.engine = create_engine(LOCAL_URL, echo=False)
db_mod.SessionLocal = db_mod.sessionmaker(bind=db_mod.engine)

from storage.db import init_db
init_db()

from services.transcription_service import get_openai_client
from services.synthesis_service import synthesize
from storage.fragments_db import (
    search_by_embedding, search_hybrid, get_latest_cluster_version,
    get_fragments_clusters, get_cluster_fragments, save_artifact,
)

# Parse topic from args
topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
if not topic:
    print("Usage: python scripts/test_synthesis.py \"тема\"")
    print("Example: python scripts/test_synthesis.py чайный бизнес")
    sys.exit(1)

print(f"\n{'='*60}")
print(f"Topic: {topic}")
print(f"{'='*60}\n")

# 1. Embed query
print("1. Embedding query...")
client = get_openai_client()
resp = client.embeddings.create(model="text-embedding-3-small", input=topic)
query_embedding = resp.data[0].embedding

# 2. Search
print("2. Searching fragments...")
results = search_by_embedding(query_embedding, limit=30)
print(f"   Found {len(results)} fragments by semantic search")

if not results:
    print("No fragments found. Exiting.")
    sys.exit(0)

# 3. Cluster context
print("3. Checking cluster context...")
version = get_latest_cluster_version()
all_fragments = {r['id']: r for r in results}
primary_cluster_id = None
primary_cluster_name = None

if version:
    frag_ids = [r['id'] for r in results]
    cluster_map = get_fragments_clusters(frag_ids, version)

    cluster_counts = {}
    for fid, cl in cluster_map.items():
        cluster_counts[cl['id']] = cluster_counts.get(cl['id'], 0) + 1

    if cluster_counts:
        primary_cluster_id = max(cluster_counts, key=cluster_counts.get)
        primary_cluster_name = cluster_map[
            next(fid for fid, cl in cluster_map.items() if cl['id'] == primary_cluster_id)
        ]['name']

        cluster_frags = get_cluster_fragments(primary_cluster_id, limit=500)
        for cf in cluster_frags:
            if cf['id'] not in all_fragments:
                all_fragments[cf['id']] = cf

        print(f"   Primary cluster: {primary_cluster_name} (id={primary_cluster_id})")
        print(f"   Added {len(cluster_frags)} cluster fragments")

print(f"   Total unique fragments: {len(all_fragments)}")

# 4. Sort by date
fragments = sorted(all_fragments.values(), key=lambda f: f.get('created_at', ''))

# Show fragment previews
print(f"\n--- Fragments ({len(fragments)}) ---")
for i, f in enumerate(fragments[:5], 1):
    date = str(f.get('created_at', ''))[:10]
    preview = f['text'][:80].replace('\n', ' ')
    print(f"  {i}. [{f['id']}] {date}: {preview}...")
if len(fragments) > 5:
    print(f"  ... and {len(fragments) - 5} more")

# 5. Synthesize
print(f"\n4. Synthesizing (GPT)...")
result = synthesize(topic, fragments)

print(f"\n{'='*60}")
print(f"ARTIFACT: «{topic}»")
print(f"Fragments used: {len(result['fragment_ids'])}")
print(f"Model: {result['model']}")
print(f"{'='*60}\n")
print(result['content'])
print(f"\n{'='*60}")
print(f"Content length: {len(result['content'])} chars")
