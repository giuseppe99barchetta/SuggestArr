"""SQL for "may the caller see or decide this pending request?".

Shared by the queue and the feedback mixins; the rule itself is explained in
``api_service.utils.request_scope``.
"""


def payload_user_expression(db_type, column='payload', field='_user_id'):
    """Read a server-selected field from a JSON payload column; defaults to media user."""
    if db_type == 'postgres':
        return f"({column}::jsonb ->> '{field}')"
    if db_type in ('mysql', 'mariadb'):
        return f"JSON_UNQUOTE(JSON_EXTRACT({column}, '$.{field}'))"
    return f"json_extract({column}, '$.{field}')"


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
