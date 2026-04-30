import time
from typing import List, Dict

def original_merge(ai_movies: List[Dict], ai_tv: List[Dict]) -> List[Dict]:
    merged: List[Dict] = []
    for pair in zip(ai_movies, ai_tv):
        merged.extend(pair)

    # Append leftovers (when one list is longer than the other)
    for lst in (ai_movies, ai_tv):
        for item in lst:
            if item not in merged:
                merged.append(item)
    return merged

def optimized_merge(ai_movies: List[Dict], ai_tv: List[Dict]) -> List[Dict]:
    merged: List[Dict] = []
    seen = set()
    for pair in zip(ai_movies, ai_tv):
        for item in pair:
            item_id = id(item)
            if item_id not in seen:
                merged.append(item)
                seen.add(item_id)

    for lst in (ai_movies, ai_tv):
        for item in lst:
            item_id = id(item)
            if item_id not in seen:
                merged.append(item)
                seen.add(item_id)
    return merged

def slicing_merge(ai_movies: List[Dict], ai_tv: List[Dict]) -> List[Dict]:
    min_len = min(len(ai_movies), len(ai_tv))
    merged: List[Dict] = []
    for i in range(min_len):
        merged.append(ai_movies[i])
        merged.append(ai_tv[i])
    merged.extend(ai_movies[min_len:])
    merged.extend(ai_tv[min_len:])
    return merged

# Generate large data
ai_movies = [{"id": i, "media_type": "movie"} for i in range(5000)]
ai_tv = [{"id": i, "media_type": "tv"} for i in range(2000)]

start = time.time()
res1 = original_merge(ai_movies, ai_tv)
print("Original:", time.time() - start)

start = time.time()
res2 = optimized_merge(ai_movies, ai_tv)
print("Optimized (set):", time.time() - start)

start = time.time()
res3 = slicing_merge(ai_movies, ai_tv)
print("Slicing:", time.time() - start)

print("Results match:", res1 == res2 == res3)
