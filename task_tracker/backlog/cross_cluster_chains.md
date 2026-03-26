# Cross-cluster chains (inter-cluster relationships)

## Problem
DBSCAN creates isolated clusters. Real thought chains often cross topics:
- #aretea (tea business) + #idea (business models) + #ayda_run (running product)
  → chain "how I think about launching a product"

## Approaches

### A. Cluster centroid distance
- Calculate average distance between cluster centroids
- If two clusters are close (distance < 0.4) → "related"
- Simple but coarse

### B. Meta-clustering
- First pass: DBSCAN with small eps → many small clusters
- Second pass: DBSCAN on cluster centroids with larger eps → meta-groups
- "Meta-cluster: product launch" contains clusters "tea", "running", "packaging"

### C. GPT cross-cluster synthesis (most powerful)
- Give GPT previews of 10-20 clusters
- Ask to find cross-cutting themes
- "I see clusters 3, 7, 12 are all about your fear of starting"
- Most powerful but costs more

### D. Tag overlap
- Fragments with shared tags across different clusters → potential connection
- Data already available, no GPT needed

## When
Etap 6 (patterns & synthesis) — approaches A and D are simple to add.
Approach C fits naturally with synthesis_service.py.
