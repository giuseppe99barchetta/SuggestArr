## 2023-10-27 - Batching Concurrent API Requests
**Learning:** Naively applying `asyncio.gather` on large lists (like TMDB API results) removes the ability to short-circuit when a required number of results is found. This leads to eager over-fetching, wasted API calls, and a higher risk of rate limiting.
**Action:** When parallelizing API calls inside a loop with an early-exit condition (e.g., reaching `search_size`), group the concurrent requests into small batches (e.g., `batch_size = 5`). This balances concurrency with avoiding massive over-fetching.
