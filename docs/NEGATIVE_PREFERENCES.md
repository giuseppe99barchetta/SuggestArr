# Negative Preferences — Current State and Proposal

**Status:** research and design notes. Nothing here is implemented beyond what
the "What exists today" section describes.

A user cannot currently tell SuggestArr *"I don't like this show."* There are
several partial mechanisms, but none of them is a preference signal, and the
one place the system already understands negative preference is never fed. This
document records exactly what exists, why the gaps matter, and what could be
built to close them.

---

## The question this answers

Two related but distinct things a user wants:

1. **"Never recommend this to me."** Suppress a title as a *result*.
2. **"Don't use this as a source."** Stop a title influencing what gets
   recommended — it should not act as a seed.

A show you abandoned after two episodes is the case where both matter at once,
and today neither is properly expressible.

---

## What exists today

### The suggestion blacklist — a block, not a preference

`suggestion_blacklist` is keyed on `(tmdb_id, media_type)` and is the only
durable "never again" store.

It is enforced in exactly one place, at the moment a request is queued:

```120:121:api_service/db/components/request_queue_mixin.py
        if self.is_suggestion_blacklisted(tmdb_id, media_type):
            return False
```

Consequences of that single enforcement point:

- The recommendation pipeline still runs to completion for a blacklisted
  title. TMDb lookups and, in LLM mode, model tokens are spent producing a
  suggestion that is then discarded silently at the door.
- It never influences *future* recommendations. Blacklisting a slasher film
  does not make the next run any less likely to suggest three more.
- It is **installation-wide**, not per user. One person's blacklist entry
  suppresses that title for everybody.
- It is written from the request workflow as a bulk action. There is no
  per-card "never suggest this" control, and the frontend never calls
  `POST /api/jobs/suggestions/blacklist` at all.

The blacklist is best understood as an operator tool for keeping junk out of
Seer, not as a taste signal.

### Rejecting a suggestion is weaker still

Rejecting archives the pending row without writing a blacklist entry. The title
is blocked from re-enqueue only while that row survives, and "request again"
clears it. Reject and blacklist are deliberately separate actions.

### Simkl status — the one working "don't seed this" lever

Simkl statuses are the only place a user action already changes what feeds
recommendations, though as a side effect rather than a designed feature:

```28:36:api_service/services/simkl/watch_history_sync.py
# Statuses worth caching. plantowatch is deliberately absent: treating a
# wishlist entry as watched would suppress the exact titles a user wants.
CACHED_STATUSES = ("watching", "completed", "hold", "dropped")

# A title being worked through is a far better recommendation seed than one
# finished long ago, so seeds span both. Exclusions stay strict: only a
# finished title should suppress a recommendation.
SEED_STATUSES = ("watching", "completed")
EXCLUSION_STATUSES = ("completed",)
```

| Simkl status | Cached | Seeds recommendations | Excluded as watched |
| --- | --- | --- | --- |
| `watching` | yes | yes | no |
| `completed` | yes | yes | yes |
| `hold` | yes | no | no |
| `dropped` | yes | no | no |
| `plantowatch` | no | no | no |

Marking a show **dropped** on Simkl does remove it from the seed pool. But
because exclusions are `completed`-only, dropping it also makes it eligible to
be recommended back to the user. The user has to blacklist it in SuggestArr as
well to get both halves, and nothing in the UI tells them so.

`hold` and `dropped` rows are cached and then ignored entirely. They are the
clearest existing signal of disinterest in the system, and they are inert.

### AI Search feedback — the right control, wired to the wrong scope

`ai_search_feedback` stores explicit thumbs up/down per `(tmdb_id, media_type)`,
surfaced in the AI Search page. Dislikes are folded into the exclusion set for
AI Search results:

```153:154:api_service/services/ai_search/ai_search_service.py
            disliked_ids = db.get_ai_dislike_ids(media_type)
            already_requested = already_requested | {str(i) for i in disliked_ids}
```

Likes bias the AI Search prompt. **None of this reaches recommendation jobs.** A
user who thumbs-downs a title in AI Search will still receive it from the
nightly recommendation job. This is the most surprising gap: the product already
asks the user the right question and then discards the answer everywhere else.

### The LLM already understands negative preference — nothing feeds it

The prompt layer classifies each history item by preference signal:

```399:405:api_service/services/llm/llm_service.py
    signal = str(item.get("preference_signal") or "recent_watch").lower()
    if signal in {"positive", "strong_positive", "favorite", "liked"}:
        signal_label = "strong positive signal"
    elif signal in {"negative", "disliked"}:
        signal_label = "negative signal"
    else:
        signal_label = "recent/neutral watch"
```

The prompt instructs the model to treat a neutral watch as weak evidence and not
to extrapolate from negative signals. But the field is only ever read, never
written:

```232:232:api_service/handler/base_handler.py
            "preference_signal": seed.get("preference_signal", "recent_watch"),
```

No seed builder — Plex, Jellyfin, Emby, Trakt, or Simkl — sets it. The only
assignment anywhere in the repository is a test fixture. Every seed reaches the
model as `recent_watch`.

This is the cheapest available win: the consumer is written and tested, and only
the producer is missing.

### Ratings are read, but only for file cleanup

Cleanup automation reads Plex `userRating` and Jellyfin/Emby `IsFavorite` to
decide which files to keep. `FAVORITE_USER_RATING = 10.0` means "do not delete."
Nothing in the recommendation path reads ratings from any provider. Trakt and
Simkl rating endpoints are never called.

So a user who rates a show one star in Plex has expressed a clear opinion that
the system reads, uses to decide file retention, and never applies to
recommendations.

### Content filters

Genre exclusion exists globally (`FILTER_GENRES_EXCLUDE`) and per job
(`without_genres`). There is no keyword exclusion and no per-title exclusion
list on a job.

---

## Summary of gaps

| Capability | State |
| --- | --- |
| Never recommend this title | Blacklist only: global, enqueue-time, bulk-only UI |
| Don't use this title as a seed | Simkl `dropped`/`hold` only; no equivalent for Plex, Jellyfin, Emby, or Trakt |
| Per-user preferences | Does not exist; blacklist and AI Search feedback are both installation-wide |
| Negative signal to the LLM | Consumer implemented, producer missing |
| Ratings as preference | Read for cleanup only, never for recommendations |
| Dislike affects recommendation jobs | Does not exist; AI Search feedback is siloed |

---

## Proposal

Four increments, ordered by value per unit of risk. Each stands alone and is
useful without the ones after it.

### 1. Feed `preference_signal` from signals already in the database

**Problem:** the LLM is told every seed is neutral.

Set the field where seeds are built:

- Simkl `dropped` → `negative` (the user abandoned it).
- Simkl `completed` → keep `recent_watch`. Finishing something is not proof of
  enjoyment, which is the existing and correct stance.
- AI Search thumbs down on a title that also appears in history → `negative`.
- AI Search thumbs up → `liked`.

Nothing new to store and no new UI. Requires including `dropped` rows in the
seed query while tagging them negative, so they inform the prompt without
becoming recommendation sources — a distinction the current `SEED_STATUSES`
constant cannot express and which would need splitting into "titles to send to
the LLM" versus "titles to expand via TMDb similarity."

**Caveat worth stating plainly:** this only affects LLM mode. The TMDb
similarity path has no notion of preference and would be unchanged.

### 2. Promote AI Search feedback into a shared preference store

**Problem:** the user's most explicit signal is confined to one page.

Rename the concept from "AI Search feedback" to a general title-preference
store, and read dislikes as an exclusion in recommendation jobs as well as AI
Search. The table already has the right shape.

Two decisions to make first:

- Should an AI Search dislike suppress a title in recommendation jobs
  automatically, or should that be an opt-in job filter? Automatic is more
  intuitive; opt-in avoids surprising anyone relying on today's behaviour.
- The table is global. If per-user preferences are wanted (increment 4), it is
  cheaper to add `user_id` before this store gains more callers than after.

### 3. A real "not interested" control on suggestions

**Problem:** blacklisting is a bulk operator action, discoverable only in the
request workflow, and it teaches the system nothing.

Add a per-card action on a suggestion that records a *disliked* preference and
suppresses the title, distinct from the existing operator blacklist. Enforce it
early in the recommendation pipeline rather than at enqueue, so the pipeline
stops wasting TMDb calls and LLM tokens on titles that will be dropped.

Keep the operator blacklist as-is. The two have genuinely different meanings —
"this does not belong in my library" versus "this is not to my taste" — and
merging them would lose that.

### 4. Make preferences per-user

**Problem:** one person's dislike currently silences a title for the whole
installation.

Key preferences on the media-user identity, matching how Trakt and Simkl links
already work. This is the largest change because it touches the blacklist's
primary key and every read path, which is exactly why increments 2 and 3 should
settle the storage shape first if per-user is the eventual goal.

---

## Suggested first step

Increment 1 is the natural opening move: it makes the abandoned-show case work
end to end in LLM mode, uses only data already synced, adds no schema and no UI,
and forces the useful conceptual split between "a title the model should know
about" and "a title worth expanding into similar content."

Increment 2 delivers the most user-visible value for its size, but decide the
per-user question before it acquires more callers.
