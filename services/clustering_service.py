"""
Clustering service: UMAP + HDBSCAN clustering of fragment embeddings.
Groups semantically similar fragments into clusters (chains).
Pipeline: 1536-dim embeddings → UMAP(50 dims) → HDBSCAN.
"""

import logging
from collections import Counter

import numpy as np
import hdbscan
import umap

from storage.fragments_db import (
    get_all_embedded_fragments,
    get_latest_cluster_version,
    save_cluster_results,
)

logger = logging.getLogger(__name__)

# UMAP defaults
UMAP_N_COMPONENTS = 50
UMAP_N_NEIGHBORS = 15
UMAP_RANDOM_STATE = 42


def run_clustering(min_cluster_size: int = 5, min_samples: int = 3) -> dict:
    """Run UMAP dimensionality reduction + HDBSCAN clustering.

    Args:
        min_cluster_size: minimum number of fragments to form a cluster
        min_samples: controls how conservative clustering is (higher = more noise)

    Returns:
        {version, n_clusters, n_noise, n_total,
         clusters: [{label, size, preview}, ...] (top 20 by size)}
    """
    # 1. Load all embeddings
    fragments = get_all_embedded_fragments()
    if not fragments:
        return {'version': 0, 'n_clusters': 0, 'n_noise': 0, 'n_total': 0, 'clusters': []}

    n_total = len(fragments)
    logger.info(f"Clustering {n_total} fragments (min_cluster_size={min_cluster_size}, min_samples={min_samples})")

    # 2. Build numpy matrix
    ids = [f['id'] for f in fragments]
    matrix = np.array([f['embedding'] for f in fragments])

    # 3. UMAP: reduce 1536 dims → 50 dims (cosine metric preserves semantic similarity)
    logger.info(f"UMAP reducing {matrix.shape[1]} → {UMAP_N_COMPONENTS} dimensions")
    reducer = umap.UMAP(
        n_components=UMAP_N_COMPONENTS,
        metric='cosine',
        n_neighbors=UMAP_N_NEIGHBORS,
        min_dist=0.0,
        random_state=UMAP_RANDOM_STATE,
    )
    reduced = reducer.fit_transform(matrix)

    # 4. HDBSCAN on reduced embeddings (euclidean works well after UMAP)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean',
        cluster_selection_method='eom',
    )
    labels = clusterer.fit_predict(reduced)

    # 5. Group fragments by label
    cluster_map = {}  # label -> [indices]
    n_noise = 0
    for idx, label in enumerate(labels):
        if label == -1:
            n_noise += 1
            continue
        cluster_map.setdefault(label, []).append(idx)

    n_clusters = len(cluster_map)
    logger.info(f"HDBSCAN result: {n_clusters} clusters, {n_noise} noise fragments")

    # 6. Build cluster data
    version = (get_latest_cluster_version() or 0) + 1
    clusters_data = []

    for label, indices in sorted(cluster_map.items()):
        fragment_ids = [ids[i] for i in indices]
        cluster_fragments = [fragments[i] for i in indices]

        # Preview: most common tag + first 2 fragments text
        preview = _make_preview(cluster_fragments)

        clusters_data.append({
            'label': int(label),
            'size': len(fragment_ids),
            'preview': preview,
            'fragment_ids': fragment_ids,
        })

    # Sort by size DESC for saving
    clusters_data.sort(key=lambda c: c['size'], reverse=True)

    # 7. Save to DB
    save_cluster_results(version, clusters_data)
    logger.info(f"Saved clustering v{version}: {n_clusters} clusters")

    return {
        'version': version,
        'n_clusters': n_clusters,
        'n_noise': n_noise,
        'n_total': n_total,
        'clusters': [
            {'label': c['label'], 'size': c['size'], 'preview': c['preview']}
            for c in clusters_data[:20]
        ],
    }


def _make_preview(cluster_fragments: list[dict]) -> str:
    """Generate cluster preview: most common tag + first 2 fragment texts."""
    # Find most common tag
    all_tags = []
    for f in cluster_fragments:
        all_tags.extend(f.get('tags') or [])

    top_tag = ""
    if all_tags:
        top_tag = Counter(all_tags).most_common(1)[0][0]

    # Sort by date, take first 2
    sorted_frags = sorted(cluster_fragments, key=lambda f: f['created_at'])
    texts = []
    for f in sorted_frags[:2]:
        t = f['text'][:80].replace('\n', ' ').strip()
        if len(f['text']) > 80:
            t += "..."
        texts.append(t)

    preview = " | ".join(texts)
    if top_tag:
        preview = f"{top_tag}: {preview}"

    return preview
