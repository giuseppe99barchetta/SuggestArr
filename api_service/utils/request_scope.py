"""Who may see and decide which suggestions.

Answered once for every blueprint that lists or decides suggestions (the
workflow routes, the public API, the legacy job routes):

* Visibility — ``REQUEST_VISIBILITY``:
    ``all``      everyone sees every request (the default),
    ``own``      regular users see only requests from their linked media
                 accounts, admins still see everything,
    ``own_all``  admins are limited as well.  Admin rights stay as they are;
                 only the request views are narrowed.

* Ownership — ``pending_requests.owner_id``, fixed when the suggestion is
  queued (see ``DatabaseManager.resolve_suggestion_owner``): the owner of the
  job, or for a job without an owner the SuggestArr user with a *verified*
  link to the media user whose history produced it.  A self-selected link
  proves nothing and never grants ownership.  Suggestions nobody could be
  resolved for stay unassigned (``owner_id`` NULL).

  Regular users decide only what they own.  Admins decide everything, except
  under ``own_all``, where they decide what they own plus the unassigned
  suggestions — otherwise those could never be approved by anyone.
"""
from dataclasses import dataclass
from typing import List, Optional

VISIBILITY_MODES = ('all', 'own', 'own_all')


@dataclass(frozen=True)
class SuggestionScope:
    """
    The rows of ``pending_requests`` a user may list and decide.

    Attributes:
        owner_id:           Restrict to this owner, or None for no owner filter.
        include_unassigned: Also include rows without an owner.
        media_user_ids:     Restrict to rows from these media users, or None.
                            An empty list matches nothing.
    """
    owner_id: Optional[int]
    include_unassigned: bool
    media_user_ids: Optional[List[str]]


def visibility_mode(env):
    """Return the configured visibility mode, falling back to ``all``."""
    value = (env or {}).get('REQUEST_VISIBILITY', 'all')
    return value if value in VISIBILITY_MODES else 'all'


def _is_admin(user):
    return (user or {}).get('role') == 'admin'


def is_restricted(user, env):
    """True when this user sees only requests from their own linked accounts."""
    mode = visibility_mode(env)
    if mode == 'own_all':
        return True
    return mode == 'own' and not _is_admin(user)


def linked_media_user_ids(db, user):
    """External media-user ids linked to this SuggestArr user, as strings."""
    return [str(profile['external_user_id']) for profile in db.get_user_media_profiles(int(user['id']))]


def visible_request_user_ids(db, user, env, selected=''):
    """
    Media-user ids whose requests this user may see.

    Returns:
        None for no restriction, otherwise a list (possibly empty, which
        matches nothing).  A selected id narrows the result, but never widens
        a restricted user beyond their own accounts.
    """
    selected = (selected or '').strip()
    if not is_restricted(user, env):
        return [selected] if selected else None
    linked = linked_media_user_ids(db, user)
    return [selected] if selected and selected in linked else linked


def suggestion_scope(db, user, env, selected=''):
    """
    Build the scope for listing and deciding suggestions.

    Args:
        db:       Database manager (for the user's linked media accounts).
        user:     The authenticated user (``g.current_user``).
        env:      Runtime configuration.
        selected: Optional media-user id to narrow the list to.

    Returns:
        SuggestionScope
    """
    if _is_admin(user):
        selected = (selected or '').strip()
        media_user_ids = [selected] if selected else None
        if visibility_mode(env) == 'own_all':
            # Ownership decides for an admin here, not the media account a
            # suggestion came from: an unassigned suggestion from someone
            # else's history must stay reachable.
            return SuggestionScope(int(user['id']), True, media_user_ids)
        return SuggestionScope(None, False, media_user_ids)
    return SuggestionScope(int(user['id']), False, visible_request_user_ids(db, user, env, selected))
