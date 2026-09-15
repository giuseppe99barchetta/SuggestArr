"""SQL for "may the caller see or decide this pending request?".

Shared by the queue and the feedback mixins; the rule itself is explained in
``api_service.utils.request_scope``.
"""


def payload_user_expression(db_type, column='payload'):
    """SQL expression reading ``_user_id`` from a JSON payload column."""
    if db_type == 'postgres':
        return f"({column}::jsonb ->> '_user_id')"
    if db_type in ('mysql', 'mariadb'):
        return f"JSON_UNQUOTE(JSON_EXTRACT({column}, '$._user_id'))"
    return f"json_extract({column}, '$._user_id')"


def ownership_clause(db_type, owner_id, include_unassigned=False, prefix=''):
    """
    Build the owner restriction for ``pending_requests``.

    Args:
        db_type: 'sqlite', 'postgres', 'mysql' or 'mariadb'.
        owner_id: The caller's SuggestArr id, or None for no restriction.
        include_unassigned: Also match rows without an owner.
        prefix: Table alias including the dot, e.g. ``'p.'``.

    Returns:
        tuple: (clause starting with " AND ", or "", list of parameters)
    """
    if owner_id is None:
        return '', []
    ph = '%s' if db_type in ('mysql', 'mariadb', 'postgres') else '?'
    if include_unassigned:
        return f" AND ({prefix}owner_id={ph} OR {prefix}owner_id IS NULL)", [owner_id]
    return f" AND {prefix}owner_id={ph}", [owner_id]
