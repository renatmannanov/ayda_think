# Auto-normalize fragments on insert

## Problem

tg_gather writes fragments directly to PostgreSQL (asyncpg INSERT), bypassing
`POST /api/fragments` endpoint which has auto-normalization built in.
Result: new fragments arrive with `embedding = NULL` and stay that way.

## Current state

- 1190 fragments without embeddings (from tg_gather / iwacado)
- 686 fragments with embeddings (processed earlier)
- `/normalize` bot command works manually (admin only)
- `POST /api/fragments` auto-normalizes, but tg_gather doesn't use it

## Options (ranked)

### Option A: tg_gather calls POST /api/normalize (recommended)

Add a lightweight `POST /api/normalize` endpoint to ayda_think that triggers
`normalize_all()`. tg_gather calls it after each batch.

**Pros:** normalization runs exactly when needed, minimal changes
**Cons:** tg_gather needs AYDA_API_URL + FRAGMENTS_API_KEY env vars

Changes:
- ayda_think: add `POST /api/normalize` endpoint (5 lines)
- tg_gather: add HTTP call after insert (httpx/aiohttp, ~10 lines)

### Option B: tg_gather uses POST /api/fragments instead of direct INSERT

Replace asyncpg INSERT with HTTP call to existing endpoint.

**Pros:** single code path, auto-normalization already works
**Cons:** slower (HTTP vs direct DB), rewrite tg_gather's db.py

### Option C: Periodic background task in ayda_think

Run `normalize_all()` every N minutes via asyncio task or APScheduler.

**Pros:** works regardless of data source
**Cons:** wasteful polling, delay between insert and embedding

### Option D: PostgreSQL NOTIFY/LISTEN

DB trigger fires NOTIFY on INSERT, ayda_think listens and normalizes.

**Pros:** instant, no polling
**Cons:** more complex, needs asyncpg listener in ayda_think

## Decision

TBD — first verify `/normalize` works manually, then implement Option A.
