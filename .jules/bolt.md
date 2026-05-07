## 2024-05-07 - Batching sequential API calls for discoveries
**Learning:** Found an N+1 API bottleneck in `api_service/services/tmdb/tmdb_discover.py` where OMDb IMDB lookups occurred sequentially for each result page.
**Action:** Replaced sequential awaits with batched processing (size 5) using `asyncio.gather`. Always apply similar logic to list iterations requiring external asynchronous I/O if the current implementation defaults to a blocking for-loop.
