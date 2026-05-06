## 2026-05-06 - [TMDbDiscover Batching Optimization]
**Learning:** [The TMDbDiscover._discover method was fetching IMDB ids sequentially, whereas TMDbClient was successfully using asyncio.gather for this same process.]
**Action:** [I have updated TMDbDiscover._discover to use asyncio.gather with a batch size of 5 to resolve this bottleneck.]
