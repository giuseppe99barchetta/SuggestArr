"""Destination-bound credentials and minimal integration response payloads."""
from api_service.utils.ssrf_guard import normalize_base_url


def select_credentials(data, keys, load_saved, optional=()):
    """Use a saved tuple or a complete explicit tuple, never a mixture."""
    if not any(key in data for key in (*keys, *optional)):
        return load_saved()
    if any(not isinstance(data.get(key), str) or not data[key].strip()
           or data[key] == '***' for key in keys):
        raise ValueError('A complete explicit URL and credentials are required')
    return tuple(data[key].strip() for key in keys) + tuple(data.get(key) for key in optional)


def public_arr_servers(servers):
    """Never pass through service URLs, API keys or new upstream fields."""
    fields = ('id', 'name', 'is4k', 'isDefault', 'activeProfileId', 'activeProfileName',
              'activeDirectory', 'activeLanguageProfileId', 'activeAnimeProfileId',
              'activeAnimeLanguageProfileId', 'activeAnimeProfileName', 'activeAnimeDirectory')
    nested = {'profiles': ('id', 'name'), 'rootFolders': ('id', 'path'),
              'languageProfiles': ('id', 'name'), 'tags': ('id', 'label')}
    result = []
    for server in servers or []:
        item = {key: server[key] for key in fields if key in server}
        for key, allowed in nested.items():
            item[key] = [{field: row[field] for field in allowed if field in row}
                         for row in server.get(key) or [] if isinstance(row, dict)]
        result.append(item)
    return result


def bind_flat_credentials(incoming, existing):
    """Validate before placeholder merging or persistence can reuse old secrets."""
    result = dict(incoming)
    for prefix in ('PLEX', 'JELLYFIN', 'SEER'):
        url_key, token_key = f'{prefix}_API_URL', f'{prefix}_TOKEN'
        if (prefix == 'SEER' and existing.get(token_key) and token_key in result
                and result[token_key] != '***' and result[token_key] != existing.get(token_key)):
            result['SEER_SESSION_TOKEN'] = ''
        if url_key not in result or not result[url_key]:
            if url_key in result and existing.get(url_key):
                result[token_key] = ''
                if prefix == 'SEER':
                    result['SEER_SESSION_TOKEN'] = ''
            continue
        new_url = normalize_base_url(result[url_key])
        result[url_key] = new_url
        old_url = existing.get(url_key)
        try:
            old_url = normalize_base_url(old_url) if old_url else None
        except ValueError:
            old_url = None
        if existing.get(url_key) and new_url != old_url:
            token = result.get(token_key)
            if not isinstance(token, str) or not token or token == '***':
                raise ValueError('Changing an integration URL requires explicit new credentials')
            if prefix == 'SEER':
                result['SEER_SESSION_TOKEN'] = ''
                # Never carry saved login credentials to a different server.
                for key in ('SEER_USER_NAME', 'SEER_USER_PSW'):
                    if key not in result or result[key] == '***':
                        result[key] = ''
    return result
