"""Reconcile plex.tv account ids with the ids a Plex server reports.

Plex exposes the same person under two different ids. Linking a profile goes
through plex.tv OAuth, which returns the global plex.tv account id, while the
users an admin picks in Services come from the server's own account list. For
shared users the two agree, but the server *owner* is a local account — id 1 —
so their plex.tv id never appears in the server list.

Everything downstream (job augmentation, request visibility, watch-tracker
links) keys off the server's id space, so a profile stored under the plex.tv id
belongs to nobody as far as those features are concerned. Mapping the id at
link time keeps a single identity per person.
"""
from typing import Any, Callable, Dict, List, Optional, Sequence

from api_service.config.logger_manager import LoggerManager

logger = LoggerManager.get_logger(__name__)


def list_plex_server_users() -> List[Dict[str, Any]]:
    """Return the configured Plex server's users, or [] when unavailable.

    Callers treat an empty list as "cannot tell" and leave ids untouched, so a
    misconfigured or unreachable server degrades to the previous behaviour
    instead of failing a link or a boot.
    """
    from asgiref.sync import async_to_sync

    from api_service.config.config import load_env_vars
    from api_service.services.plex.plex_client import PlexClient

    env = load_env_vars()
    api_url = env.get("PLEX_API_URL")
    token = env.get("PLEX_TOKEN")
    if not api_url or not token:
        return []
    try:
        return async_to_sync(PlexClient(api_url=api_url, token=token).get_all_users)()
    except Exception as exc:
        logger.warning("Could not list Plex users to reconcile account ids: %s", exc)
        return []


def canonical_plex_account_id(
    server_users: Sequence[Dict[str, Any]],
    plex_account_id: str,
    plex_username: Optional[str] = None,
) -> str:
    """Return the id the configured Plex server uses for this account.

    :param server_users: Users as reported by the server, each ``{id, name}``.
    :param plex_account_id: The plex.tv account id from OAuth.
    :param plex_username: The plex.tv username, used to match the owner's
        local account when the ids differ.
    :return: The server-side id when one can be identified, otherwise
        ``plex_account_id`` unchanged.

    Falls back to the plex.tv id whenever the match is not certain: a wrong
    match would attach one person's watch history to another, which is far
    worse than leaving an id that simply resolves to nothing.
    """
    account_id = str(plex_account_id)
    if not server_users:
        return account_id

    if any(str(user.get("id")) == account_id for user in server_users):
        return account_id

    target = str(plex_username or "").strip().casefold()
    if not target:
        return account_id

    matches = [
        str(user.get("id"))
        for user in server_users
        if str(user.get("name") or "").strip().casefold() == target
    ]
    # Ambiguity means the name is not a reliable key on this server, so no
    # guess is made.
    if len(matches) == 1:
        return matches[0]
    return account_id


def reconcile_plex_profiles(db, list_server_users: Callable[[], List[Dict[str, Any]]]) -> int:
    """Repair Plex profiles stored under a plex.tv id the server does not use.

    Reconciliation happens when a profile is linked, but profiles created
    before that existed are still stranded, and their owners have no way to
    tell: the UI simply reports that nothing is linked. This re-points them so
    they work without anyone re-linking.

    :param db: DatabaseManager-like object.
    :param list_server_users: Callable returning the server's ``{id, name}``
        users. Called once, and only when there is a profile to check.
    :return: Number of profiles repaired.

    Renaming the identity rather than recreating it preserves any Trakt or
    Simkl links already attached to it.
    """
    profiles = db.get_media_profiles_by_provider("plex")
    if not profiles:
        return 0

    server_users = list_server_users()
    if not server_users:
        return 0

    # user_media_profiles is unique only on (user_id, provider), so nothing in
    # the schema stops two SuggestArr accounts from being re-pointed at one
    # Plex user. That would merge two people's requests and watch history, so
    # a target another profile already holds is left for an admin to resolve.
    claimed = {
        str(profile.get("external_user_id") or ""): profile["user_id"]
        for profile in profiles
    }

    repaired = 0
    for profile in profiles:
        stored_id = str(profile.get("external_user_id") or "")
        resolved = canonical_plex_account_id(
            server_users, stored_id, profile.get("external_username"),
        )
        if resolved == stored_id:
            continue
        owner = claimed.get(resolved)
        if owner is not None and owner != profile["user_id"]:
            logger.warning(
                "Not re-pointing the Plex profile for user id=%s to server id %s: "
                "user id=%s is already linked to it",
                profile.get("user_id"), resolved, owner,
            )
            continue
        db.rename_media_user_identity("plex", stored_id, resolved)
        db.update_media_profile_external_id(profile["user_id"], "plex", resolved)
        claimed.pop(stored_id, None)
        claimed[resolved] = profile["user_id"]
        logger.info(
            "Re-pointed Plex profile for user id=%s from %s to the server id %s",
            profile.get("user_id"), stored_id, resolved,
        )
        repaired += 1
    return repaired
