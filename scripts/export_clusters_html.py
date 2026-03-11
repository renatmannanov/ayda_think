"""
Export clustering results to an interactive HTML file with tabs:
- Tab 1: Clusters by size (current view)
- Tab 2: Clusters by semantic proximity (similar clusters nearby)
- Tab 3: Hierarchy tree (compact overview)
Usage: python scripts/export_clusters_html.py [--names] (--names = generate AI names via OpenAI)
"""
import os
import sys
import io
import html
import json
from collections import Counter
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

os.environ["DATABASE_URL"] = "postgresql://postgres:localpass@localhost:5433/ayda_think"

import storage.db as db_mod
from sqlalchemy import create_engine
db_mod.DATABASE_URL = os.environ["DATABASE_URL"]
db_mod.engine = create_engine(db_mod.DATABASE_URL, echo=False)
db_mod.SessionLocal = db_mod.sessionmaker(bind=db_mod.engine)
from storage.db import init_db
init_db()

import numpy as np
import hdbscan
import umap
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import pdist
from sqlalchemy import text as sa_text


def make_tg_link(external_id):
    if not external_id or not external_id.startswith("telegram_"):
        return None
    parts = external_id.split("_", 2)
    if len(parts) < 3:
        return None
    channel_id = parts[1]
    msg_id = parts[2]
    if channel_id.startswith("-100"):
        channel_id = channel_id[4:]
    return f"https://t.me/c/{channel_id}/{msg_id}"


def load_fragments_with_links():
    session = db_mod.SessionLocal()
    try:
        rows = session.execute(sa_text(
            "SELECT id, external_id, text, tags, created_at, embedding "
            "FROM fragments "
            "WHERE embedding IS NOT NULL AND is_duplicate IS NOT TRUE "
            "ORDER BY created_at"
        )).fetchall()
        return [
            {
                'id': r[0],
                'external_id': r[1],
                'text': r[2],
                'tags': r[3] or [],
                'created_at': r[4],
                'embedding': [float(x) for x in r[5].strip('[]').split(',')],
            }
            for r in rows
        ]
    finally:
        session.close()


def generate_ai_names(cluster_infos):
    """Generate short AI names for clusters using GPT-4o-mini."""
    from openai import OpenAI
    client = OpenAI()

    names = {}
    for c in cluster_infos:
        # Take 5 representative fragments (spread across time)
        frags = c['fragments']
        step = max(1, len(frags) // 5)
        samples = [frags[i] for i in range(0, len(frags), step)][:5]

        sample_texts = []
        for f in samples:
            tags = ' '.join(f.get('tags') or [])
            text = f['text'][:200]
            sample_texts.append(f"{tags} {text}")

        prompt = (
            "Дай короткое название (2-4 слова, на русском) для группы заметок. "
            "Название должно отражать общую тему. Верни ТОЛЬКО название, без кавычек.\n\n"
            + "\n---\n".join(sample_texts)
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=30,
                temperature=0.3,
            )
            name = resp.choices[0].message.content.strip()
            names[c['label']] = name
            tag_str = ', '.join(t for t, _ in c['top_tags'][:2])
            print(f"  [{c['size']:3d}] {tag_str} -> {name}")
        except Exception as e:
            names[c['label']] = ""
            print(f"  Error for cluster {c['label']}: {e}")

    return names


def sort_by_proximity(cluster_infos, frags, matrix):
    """Sort clusters so semantically similar ones are adjacent.
    Returns (sorted_list, group_boundaries) where group_boundaries marks
    where to draw visual separators between cluster groups.
    """
    if len(cluster_infos) < 3:
        return cluster_infos, []

    # Compute centroid for each cluster
    centroids = []
    for c in cluster_infos:
        frag_ids = {f['id'] for f in c['fragments']}
        indices = [i for i, fr in enumerate(frags) if fr['id'] in frag_ids]
        centroid = matrix[indices].mean(axis=0)
        centroids.append(centroid)

    centroids = np.array(centroids)

    # Hierarchical clustering of centroids → optimal leaf order
    dists = pdist(centroids, metric='cosine')
    Z = linkage(dists, method='average')
    order = leaves_list(Z)

    sorted_list = [cluster_infos[i] for i in order]

    # Find group boundaries: where distance between adjacent centroids jumps
    sorted_centroids = centroids[order]
    adjacent_dists = []
    for i in range(len(sorted_centroids) - 1):
        d = 1 - np.dot(sorted_centroids[i], sorted_centroids[i+1]) / (
            np.linalg.norm(sorted_centroids[i]) * np.linalg.norm(sorted_centroids[i+1]))
        adjacent_dists.append(d)

    # Use median distance as threshold for group breaks
    if adjacent_dists:
        threshold = np.percentile(adjacent_dists, 70)
        boundaries = [i + 1 for i, d in enumerate(adjacent_dists) if d > threshold]
    else:
        boundaries = []

    return sorted_list, boundaries


def run():
    use_ai_names = '--names' in sys.argv

    frags = load_fragments_with_links()
    print(f"Loaded {len(frags)} fragments")

    matrix = np.array([f['embedding'] for f in frags])

    reducer = umap.UMAP(n_components=50, metric='cosine', n_neighbors=15, min_dist=0.0, random_state=42)
    reduced = reducer.fit_transform(matrix)
    print("UMAP done")

    clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=3, metric='euclidean', cluster_selection_method='eom')
    labels = clusterer.fit_predict(reduced)
    print("HDBSCAN done")

    # Group fragments by cluster
    clusters = {}
    noise = []
    for idx, label in enumerate(labels):
        if label == -1:
            noise.append(idx)
        else:
            clusters.setdefault(label, []).append(idx)

    # Build cluster info (sorted by size)
    sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)
    cluster_infos = []
    for label, indices in sorted_clusters:
        cluster_frags = [frags[i] for i in indices]
        all_tags = []
        for f in cluster_frags:
            all_tags.extend(f.get('tags') or [])
        top_tags = Counter(all_tags).most_common(5)
        centroid = matrix[indices].mean(axis=0)
        cluster_infos.append({
            'label': label,
            'size': len(indices),
            'top_tags': top_tags,
            'fragments': sorted(cluster_frags, key=lambda f: f['created_at']),
            'centroid': centroid,
        })

    noise_frags = sorted([frags[i] for i in noise], key=lambda f: f['created_at'])
    print(f"Clusters: {len(cluster_infos)}, Noise: {len(noise_frags)}")

    # Sort by proximity
    proximity_order, prox_boundaries = sort_by_proximity(cluster_infos, frags, matrix)
    print(f"Proximity sort done ({len(prox_boundaries)} group breaks)")

    # AI names (optional)
    ai_names = {}
    if use_ai_names:
        print("Generating AI names...")
        ai_names = generate_ai_names(cluster_infos)
        print(f"Generated {len(ai_names)} names")

    generate_html(cluster_infos, proximity_order, prox_boundaries, noise_frags, len(frags), ai_names)


def frag_html(f):
    date = str(f['created_at'])[:10] if f['created_at'] else "?"
    text = html.escape(f['text'][:500])
    if len(f['text']) > 500:
        text += "..."
    text = text.replace('\n', '<br>')
    tags = ', '.join(f.get('tags') or [])
    link = make_tg_link(f.get('external_id'))

    parts = [f'<div class="frag"><span class="date">{date}</span>']
    if link:
        parts.append(f' <a href="{link}" target="_blank" class="tg-link">TG</a>')
    if tags:
        parts.append(f' <span class="tags">{html.escape(tags)}</span>')
    parts.append(f'<div class="text">{text}</div></div>')
    return ''.join(parts)


def cluster_row_html(i, c, ai_names, border_color='#3498db'):
    tag_str = ', '.join(f'{t}({n})' for t, n in c['top_tags'])
    frags_html = '\n'.join(frag_html(f) for f in c['fragments'])
    name = ai_names.get(c['label'], '')
    name_html = f'<span class="ai-name">{html.escape(name)}</span> ' if name else ''
    return f"""
        <div class="cluster">
            <div class="cluster-header" onclick="toggle(this)" style="border-left-color:{border_color}">
                <span class="arrow" style="color:{border_color}">&#9654;</span>
                <span class="num" style="color:{border_color}">#{i+1}</span>
                <span class="size" style="background:{border_color}">[{c['size']}]</span>
                {name_html}<span class="tag-summary">{html.escape(tag_str)}</span>
            </div>
            <div class="cluster-body" style="display:none">
                {frags_html}
            </div>
        </div>"""


def tree_row_html(i, c, ai_names):
    tag_str = ', '.join(f'{t}({n})' for t, n in c['top_tags'][:3])
    name = ai_names.get(c['label'], '')
    name_html = f'<span class="ai-name">{html.escape(name)}</span> ' if name else ''
    bar_width = min(c['size'] * 2, 400)
    return f"""<div class="tree-row">
        <span class="num">#{i+1}</span>
        <span class="size">[{c['size']}]</span>
        {name_html}<span class="tag-summary">{html.escape(tag_str)}</span>
        <div class="bar" style="width:{bar_width}px"></div>
    </div>"""


def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def build_hierarchy_tree(clusters, ai_names):
    """Build a nested tree: large clusters contain nearest medium, medium contain nearest small."""
    large = [c for c in clusters if c['size'] >= 30]
    medium = [c for c in clusters if 10 <= c['size'] < 30]
    small = [c for c in clusters if c['size'] < 10]

    def find_nearest(cluster, targets):
        if not targets:
            return None
        best = max(targets, key=lambda t: cosine_sim(cluster['centroid'], t['centroid']))
        return best

    # Assign each small cluster to its nearest medium (if any) or large
    # Assign each medium cluster to its nearest large
    # Build: large -> [medium -> [small]]

    # medium -> list of children (small clusters)
    medium_children = {c['label']: [] for c in medium}
    # large -> list of children (medium clusters)
    large_children = {c['label']: [] for c in large}

    # Assign small → nearest medium or large
    parents_pool = medium + large  # prefer medium first by proximity
    for s in small:
        parent = find_nearest(s, parents_pool)
        if parent and parent['label'] in medium_children:
            medium_children[parent['label']].append(s)
        elif parent and parent['label'] in large_children:
            large_children[parent['label']].append(s)

    # Assign medium → nearest large
    for m in medium:
        parent = find_nearest(m, large)
        if parent:
            large_children[parent['label']].append(m)

    # Build HTML
    tree_parts = []
    global_idx = [0]

    def render_leaf(c, depth):
        global_idx[0] += 1
        idx = global_idx[0]
        name = ai_names.get(c['label'], '')
        name_html = f'<span class="ai-name">{html.escape(name)}</span> ' if name else ''
        tag_str = ', '.join(f'{t}({n})' for t, n in c['top_tags'][:3])
        bar_width = min(c['size'] * 2, 300)
        indent = depth * 24
        return f"""<div class="tree-row" style="padding-left:{indent}px">
            <span class="num">{idx}.</span>
            <span class="size">[{c['size']}]</span>
            {name_html}<span class="tag-summary">{html.escape(tag_str)}</span>
            <div class="bar" style="width:{bar_width}px"></div>
        </div>"""

    for lc in large:
        global_idx[0] += 1
        idx = global_idx[0]
        name = ai_names.get(lc['label'], '')
        name_html = f'<span class="ai-name">{html.escape(name)}</span> ' if name else ''
        tag_str = ', '.join(f'{t}({n})' for t, n in lc['top_tags'][:3])
        children = large_children.get(lc['label'], [])
        total_frags = lc['size'] + sum(ch['size'] for ch in children)

        # Build children HTML
        children_html = ''
        for ch in children:
            if ch['label'] in medium_children:
                # This is a medium cluster with its own small children
                sub_children = medium_children[ch['label']]
                sub_html = ''.join(render_leaf(sc, 3) for sc in sub_children)
                global_idx[0] += 1
                ch_idx = global_idx[0]
                ch_name = ai_names.get(ch['label'], '')
                ch_name_html = f'<span class="ai-name">{html.escape(ch_name)}</span> ' if ch_name else ''
                ch_tags = ', '.join(f'{t}({n})' for t, n in ch['top_tags'][:3])
                ch_bar = min(ch['size'] * 2, 300)
                children_html += f"""<div class="tree-row" style="padding-left:24px">
                    <span class="num">{ch_idx}.</span>
                    <span class="size">[{ch['size']}]</span>
                    {ch_name_html}<span class="tag-summary">{html.escape(ch_tags)}</span>
                    <div class="bar" style="width:{ch_bar}px"></div>
                </div>"""
                children_html += sub_html
            else:
                # Small cluster directly under large
                children_html += render_leaf(ch, 2)

        bar_width = min(lc['size'] * 2, 400)
        tree_parts.append(f"""<div class="tree-group">
            <div class="tree-group-header" onclick="toggle(this)">
                <span class="arrow">&#9654;</span>
                <span class="num">{idx}.</span>
                <span class="size" style="background:#3498db">[{lc['size']}]</span>
                {name_html}<span class="tag-summary">{html.escape(tag_str)}</span>
                <span class="tree-group-stats">{len(children)} подкластеров, {total_frags} фрагм.</span>
            </div>
            <div class="cluster-body" style="display:none">
                <div class="tree-row">
                    <div class="bar" style="width:{bar_width}px"></div>
                </div>
                {children_html}
            </div>
        </div>""")

    # Orphan medium/small (no large clusters exist — unlikely but safe)
    orphan_medium = [m for m in medium if not large]
    orphan_small = [s for s in small if not parents_pool]
    for c in orphan_medium + orphan_small:
        tree_parts.append(render_leaf(c, 0))

    return '\n'.join(tree_parts)


def generate_html(by_size, by_proximity, prox_boundaries, noise_frags, total, ai_names):
    total_in_clusters = sum(c['size'] for c in by_size)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Tab 1: by size
    size_rows = ''.join(cluster_row_html(i, c, ai_names) for i, c in enumerate(by_size))

    # Tab 2: by proximity — with group separators
    prox_parts = []
    boundary_set = set(prox_boundaries)
    group_idx = 0
    colors = ['#3498db', '#e74c3c', '#2ecc71', '#9b59b6', '#f39c12', '#1abc9c', '#e67e22', '#34495e']
    for i, c in enumerate(by_proximity):
        if i in boundary_set:
            group_idx += 1
            prox_parts.append('<div class="group-sep"></div>')
        color = colors[group_idx % len(colors)]
        prox_parts.append(cluster_row_html(i, c, ai_names, border_color=color))
    prox_rows = ''.join(prox_parts)

    # Tab 3: tree — hierarchical nesting by centroid proximity
    tree_html = build_hierarchy_tree(by_size, ai_names)

    # Noise
    noise_html = '\n'.join(frag_html(f) for f in noise_frags)

    noise_block = f"""
    <div class="noise-section">
        <div class="noise-header" onclick="toggle(this)">
            <span class="arrow">&#9654;</span>
            <span class="num">NOISE</span>
            <span class="size">[{len(noise_frags)}]</span>
            <span class="tag-summary">Фрагменты вне кластеров</span>
        </div>
        <div class="cluster-body" style="display:none">
            {noise_html}
        </div>
    </div>"""

    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Ayda Think Clusters</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f9fa; color: #333; padding: 20px; max-width: 900px; margin: 0 auto; }}
h1 {{ color: #2c3e50; margin-bottom: 5px; }}
.stats {{ color: #777; margin-bottom: 15px; font-size: 14px; }}

/* Tabs */
.tabs {{ display: flex; gap: 0; margin-bottom: 15px; border-bottom: 2px solid #ddd; }}
.tab {{ padding: 8px 18px; cursor: pointer; color: #888; border-bottom: 2px solid transparent; margin-bottom: -2px; font-size: 14px; }}
.tab:hover {{ color: #333; }}
.tab.active {{ color: #3498db; border-bottom-color: #3498db; font-weight: bold; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

.controls {{ margin-bottom: 15px; }}
.controls button {{ background: #fff; color: #555; border: 1px solid #ccc; padding: 5px 12px; margin-right: 6px; cursor: pointer; border-radius: 4px; font-size: 13px; }}
.controls button:hover {{ background: #e9ecef; }}

/* Clusters */
.cluster {{ margin-bottom: 2px; }}
.cluster-header {{ background: #fff; padding: 10px 14px; cursor: pointer; border-left: 3px solid #3498db; display: flex; align-items: center; gap: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
.cluster-header:hover {{ background: #f0f7ff; }}
.arrow {{ color: #3498db; font-size: 12px; transition: transform 0.2s; min-width: 14px; }}
.arrow.open {{ transform: rotate(90deg); }}
.num {{ color: #3498db; font-weight: bold; min-width: 28px; font-size: 13px; }}
.size {{ color: #fff; background: #3498db; padding: 1px 7px; border-radius: 10px; font-size: 12px; font-weight: bold; min-width: 32px; text-align: center; }}
.ai-name {{ color: #2c3e50; font-weight: 600; font-size: 13px; }}
.tag-summary {{ color: #999; font-size: 12px; }}
.cluster-body {{ background: #fff; padding: 8px 14px; border-left: 3px solid #e0e0e0; }}
.frag {{ padding: 8px 0; border-bottom: 1px solid #f0f0f0; }}
.frag:last-child {{ border-bottom: none; }}
.date {{ color: #e67e22; font-size: 12px; font-weight: bold; }}
.tg-link {{ color: #3498db; font-size: 11px; text-decoration: none; margin-left: 4px; background: #eaf4fd; padding: 1px 6px; border-radius: 3px; }}
.tg-link:hover {{ text-decoration: underline; background: #d4eaf7; }}
.tags {{ color: #999; font-size: 11px; margin-left: 6px; }}
.text {{ margin-top: 4px; font-size: 14px; line-height: 1.5; color: #444; }}
.noise-section {{ margin-top: 30px; }}
.noise-header {{ background: #fff; padding: 10px 14px; cursor: pointer; border-left: 3px solid #aaa; display: flex; align-items: center; gap: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
.noise-header:hover {{ background: #f5f5f5; }}

/* Group separators (proximity tab) */
.group-sep {{ height: 12px; margin: 8px 0; border-top: 2px dashed #ccc; }}

/* Tree */
.tree-row {{ display: flex; align-items: center; gap: 8px; padding: 4px 0; border-bottom: 1px solid #f0f0f0; }}
.bar {{ height: 8px; background: #3498db; border-radius: 4px; opacity: 0.6; }}
.tree-group {{ margin-bottom: 12px; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden; }}
.tree-group-header {{ background: #f0f4f8; padding: 10px 14px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; }}
.tree-group-header:hover {{ background: #e4ebf1; }}
.tree-group-stats {{ color: #888; font-size: 12px; margin-left: auto; }}
</style>
</head>
<body>
<h1>Ayda Think — Кластеры</h1>
<div class="stats">{now} | {len(by_size)} кластеров, {len(noise_frags)} шум, {total} всего | В кластерах: {total_in_clusters} ({total_in_clusters*100//total}%)</div>

<div class="tabs">
    <div class="tab active" onclick="showTab('size')">По размеру</div>
    <div class="tab" onclick="showTab('proximity')">По близости</div>
    <div class="tab" onclick="showTab('tree')">Дерево</div>
</div>

<div id="tab-size" class="tab-content active">
    <div class="controls">
        <button onclick="expandAllIn('tab-size')">Развернуть</button>
        <button onclick="collapseAllIn('tab-size')">Свернуть</button>
    </div>
    {size_rows}
    {noise_block}
</div>

<div id="tab-proximity" class="tab-content">
    <div class="controls">
        <button onclick="expandAllIn('tab-proximity')">Развернуть</button>
        <button onclick="collapseAllIn('tab-proximity')">Свернуть</button>
    </div>
    {prox_rows}
</div>

<div id="tab-tree" class="tab-content">
    <div class="controls">
        <button onclick="expandAllIn('tab-tree')">Развернуть</button>
        <button onclick="collapseAllIn('tab-tree')">Свернуть</button>
    </div>
    {tree_html}
</div>

<script>
function toggle(header) {{
    const body = header.nextElementSibling;
    const arrow = header.querySelector('.arrow');
    if (body.style.display === 'none') {{
        body.style.display = 'block';
        if (arrow) arrow.classList.add('open');
    }} else {{
        body.style.display = 'none';
        if (arrow) arrow.classList.remove('open');
    }}
}}
function expandAllIn(tabId) {{
    document.getElementById(tabId).querySelectorAll('.cluster-body').forEach(b => b.style.display = 'block');
    document.getElementById(tabId).querySelectorAll('.arrow').forEach(a => a.classList.add('open'));
}}
function collapseAllIn(tabId) {{
    document.getElementById(tabId).querySelectorAll('.cluster-body').forEach(b => b.style.display = 'none');
    document.getElementById(tabId).querySelectorAll('.arrow').forEach(a => a.classList.remove('open'));
}}
function showTab(name) {{
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    event.target.classList.add('active');
}}
</script>
</body>
</html>"""

    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'clusters.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    run()
