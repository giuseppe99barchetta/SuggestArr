## 2026-05-05 - [Batched asyncio Requests for IMDB filtering]
**Learning:** During Discover API filtering, calling OMDB sequentially inside a `for` loop over the page result items introduces an N+1 latency bottleneck.
**Action:** Used an inner `async def` processor alongside `asyncio.gather` in a chunked batch (e.g. 5 items) to fetch IMDB ids in parallel while satisfying max_results quotas effectively.
