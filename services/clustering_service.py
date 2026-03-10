"""
Clustering service: DBSCAN clustering of fragment embeddings.
Groups semantically similar fragments into clusters (chains).
"""

import logging
from collections import Counter

import numpy as np
from sklearn.cluster import DBSCAN

from storage.fragments_db import (
    get_all_embedded_fragments,
    get_latest_cluster_version,
    save_cluster_results,
)

logger = logging.getLogger(__name__)


def run_clustering(eps: float = 0.35, min_samples: int = 3) -> dict:
    """Run DBSCAN clustering on all embedded fragments.

    Args:
        eps: max cosine distance between neighbors (lower = stricter clusters)
        min_samples: min fragments to form a cluster

    Returns:
        {version, n_clusters, n_noise, n_total,
         clusters: [{label, size, preview}, ...] (top 20 by size)}
    """
    # 1. Load all embeddings
    fragments = get_all_embedded_fragments()
    if not fragments:
        return {'version': 0, 'n_clusters': 0, 'n_noise': 0, 'n_total': 0, 'clusters': []}

    n_total = len(fragments)
    logger.info(f"Clustering {n_total} fragments (eps={eps}, min_samples={min_samples})")

    # 2. Build numpy matrix
    ids = [f['id'] for f in fragments]
    matrix = np.array([f['embedding'] for f in fragments])

    # 3. DBSCAN
    db = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
    labels = db.fit_predict(matrix)

    # 4. Group fragments by label
    cluster_map = {}  # label -> [indices]
    n_noise = 0
    for idx, label in enumerate(labels):
        if label == -1:
            n_noise += 1
            continue
        cluster_map.setdefault(label, []).append(idx)

    n_clusters = len(cluster_map)
    logger.info(f"DBSCAN result: {n_clusters} clusters, {n_noise} noise fragments")

    # 5. Build cluster data
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

    # 6. Save to DB
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
