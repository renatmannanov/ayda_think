"""
Test HDBSCAN clustering locally without running the bot.
Usage: python scripts/test_clustering.py [min_cluster_size] [min_samples]
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

# Patch db module BEFORE init_db — override engine, Session, and DATABASE_URL
import storage.db as db_mod
from sqlalchemy import create_engine
LOCAL_URL = os.environ["DATABASE_URL"]
db_mod.DATABASE_URL = LOCAL_URL
db_mod.engine = create_engine(LOCAL_URL, echo=False)
db_mod.SessionLocal = db_mod.sessionmaker(bind=db_mod.engine)

from storage.db import init_db
init_db()

from services.clustering_service import run_clustering

# Parse args
min_cluster_size = int(sys.argv[1]) if len(sys.argv) > 1 else 5
min_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 3

print(f"\nRunning HDBSCAN: min_cluster_size={min_cluster_size}, min_samples={min_samples}\n")

result = run_clustering(min_cluster_size=min_cluster_size, min_samples=min_samples)

print(f"\n{'='*60}")
print(f"Version: {result['version']}")
print(f"Clusters: {result['n_clusters']}")
print(f"Noise: {result['n_noise']} ({result['n_noise']*100//max(result['n_total'],1)}%)")
print(f"Total: {result['n_total']}")
print(f"{'='*60}\n")

if result['clusters']:
    print("Top 20 clusters:")
    for i, c in enumerate(result['clusters'], 1):
        print(f"  {i:2d}. [{c['size']:3d} frags] {c['preview'][:100]}")

# Size distribution
sizes = [c['size'] for c in result['clusters']]
if sizes:
    print(f"\nSize stats: min={min(sizes)}, max={max(sizes)}, median={sorted(sizes)[len(sizes)//2]}, total_in_clusters={sum(sizes)}")
