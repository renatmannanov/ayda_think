# Improve hybrid search quality

## Problem
Hybrid search sometimes ranks irrelevant fragments high when they match
a common keyword (e.g., "отношения") but not the specific name/entity.

## Example
`/search отношения с Айкой` — fragment about "Величие" ranks #2 because
it contains "про отношения" in text, getting 1/2 keyword match bonus.

## Ideas to explore
- Weight rare words higher than common ones (TF-IDF-like approach)
- Use PostgreSQL full-text search (tsvector/tsquery) instead of ILIKE
- Add stop-words for very common content words (not just prepositions)
- Consider embedding model upgrade (text-embedding-3-large)
- Experiment with different semantic/keyword weight ratios
- Score based on keyword position (in first 50 chars vs deep in text)

## Current scoring formula
`final_score = semantic_score * 0.4 + 0.7 * (matched_words / total_words)`

## Files
- `storage/fragments_db.py` — search_hybrid(), search_by_keywords()
- `bot/brain_handler.py` — _parse_search_query(), _stem_keyword()
