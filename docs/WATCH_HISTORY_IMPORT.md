# Import watch history

In **Profile → Recommendation history**, a user can add titles that are no longer available from their media server. These titles are kept only against that user's linked media-server profile.

Use a UTF-8 CSV with this fixed header order:

```csv
tmdb_id,media_type,title,year,rating
27205,movie,Inception,2010,9
1396,tv,Breaking Bad,2008,10
```

- `tmdb_id`, `media_type` (`movie` or `tv`) and `title` are required.
- `year` and `rating` are optional. Ratings must be from 0 to 10.
- Reimporting the same TMDb title updates its values instead of creating a duplicate.

Imported and manually-added titles are not suggested again. Explicit ratings are included in AI recommendation context; low-rated titles are never used as a source for similar-title requests.
