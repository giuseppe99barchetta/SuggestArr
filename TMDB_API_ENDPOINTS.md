# Service Test API Endpoints

This document describes the service test API endpoints that have been added to support the configuration system. These endpoints allow testing connections to various external services used by SuggestArr.

## TMDB Endpoints

### POST `/api/tmdb/test`

Tests the TMDB API connection with a provided API key.

**Request Body:**
```json
{
  "api_key": "your_tmdb_api_key_here"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "message": "TMDB API connection successful!",
  "data": {
    "total_results": 20,
    "total_pages": 1
  }
}
```

**Error Responses:**
- `400 Bad Request`: Missing or invalid API key
- `401 Unauthorized`: Invalid TMDB API key
- `500 Internal Server Error`: Connection error or timeout

## Plex Endpoints

### POST `/api/plex/test`

Tests the Plex server connection with provided API token and URL.

**Request Body:**
```json
{
  "token": "your_plex_token_here",
  "api_url": "http://localhost:32400"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "message": "Plex connection successful!",
  "data": {
    "libraries_count": 5,
    "server_url": "http://localhost:32400"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Missing token or URL, or connection failed
- `500 Internal Server Error`: Internal error

## Jellyfin Endpoints

### POST `/api/jellyfin/test`

Tests the Jellyfin server connection with provided API token and URL.

**Request Body:**
```json
{
  "token": "your_jellyfin_token_here",
  "api_url": "http://localhost:8096"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "message": "Jellyfin connection successful!",
  "data": {
    "libraries_count": 3,
    "server_url": "http://localhost:8096"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Missing token or URL, or connection failed
- `500 Internal Server Error`: Internal error

## Overseer/Jellyseer Endpoints

### POST `/api/seer/test`

Tests the Overseer/Jellyseer API connection with provided API key and URL.

**Request Body:**
```json
{
  "token": "your_seer_token_here",
  "api_url": "http://localhost:5055",
  "session_token": "optional_session_token_here"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "message": "Overseer/Jellyseer connection successful!",
  "data": {
    "users_count": 4,
    "server_url": "http://localhost:5055",
    "http_status": 200
  }
}
```

**Error Responses:**
- `400 Bad Request`: Missing token or URL, invalid credentials, or connection failed
- `500 Internal Server Error`: Internal error

*Note: The Overseer test performs a two-stage validation: first a direct HTTP test, then a client API test to ensure full functionality.*

## Common Usage Example

```javascript
async function testServiceConnection(service, config) {
  const endpoint = `/api/${service}/test`;

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config)
  });

  const result = await response.json();
  if (result.status === 'success') {
    console.log(`${service} connection successful!`);
    return result;
  } else {
    console.error(`${service} connection failed:`, result.message);
    throw new Error(result.message);
  }
}

// Example usage:
try {
  await testServiceConnection('tmdb', { api_key: 'your_api_key' });
  await testServiceConnection('plex', {
    token: 'your_plex_token',
    api_url: 'http://localhost:32400'
  });
} catch (error) {
  console.error('Service test failed:', error);
}
```

## Validation Improvements

All service test endpoints have been enhanced with robust validation:

### **Before (Problematic)**
- ✅ TMDB: Direct HTTP test - already working correctly
- ❌ Plex: Only checked if request didn't throw exception
- ❌ Jellyfin: Only checked if request didn't throw exception
- ❌ Overseer: Only checked if client didn't return None (false positives)

### **After (Fixed)**
- ✅ **TMDB**: Direct HTTP test with proper response validation
- ✅ **Plex**: Validates that actual libraries data is returned
- ✅ **Jellyfin**: Validates that actual libraries data is returned
- ✅ **Overseer**: Two-stage validation:
  1. Direct HTTP test for basic connectivity
  2. Client API test for full functionality

### **Error Handling Improvements**
- **Proper Authentication Detection**: Invalid API keys are now correctly identified
- **Data Validation**: Tests verify that actual data (not just empty responses) is returned
- **Detailed Error Messages**: Clear distinction between different failure types
- **Fast Failure**: Invalid credentials are detected quickly without long timeouts

### **Response Examples**

**Invalid API Key (Overseer):**
```json
{
  "status": "error",
  "message": "HTTP test failed: Invalid API key"
}
```

**Invalid Server URL:**
```json
{
  "status": "error",
  "message": "HTTP test failed: Connection error: Name or service not known"
}
```

**Valid but Empty Response:**
```json
{
  "status": "success",
  "message": "Overseer/Jellyseer connection successful but no users found",
  "data": {
    "users_count": 0,
    "server_url": "http://localhost:5055"
  }
}
```

### GET `/api/tmdb/genres/movie`

Gets a list of movie genres from TMDB.

**Query Parameters:**
- `api_key` (required): Your TMDB API key

**Success Response (200):**
```json
{
  "status": "success",
  "genres": [
    {
      "id": 28,
      "name": "Action"
    },
    {
      "id": 12,
      "name": "Adventure"
    },
    // ... more genres
  ]
}
```

### GET `/api/tmdb/genres/tv`

Gets a list of TV show genres from TMDB.

**Query Parameters:**
- `api_key` (required): Your TMDB API key

**Success Response (200):**
```json
{
  "status": "success",
  "genres": [
    {
      "id": 10759,
      "name": "Action & Adventure"
    },
    {
      "id": 16,
      "name": "Animation"
    },
    // ... more genres
  ]
}
```

## Frontend Integration

The TMDB API endpoints are integrated into the SettingsPage component:

1. **SettingsServices.vue**: Contains the TMDB API key input field and test button
2. **SettingsPage.vue**: Handles the `test-connection` event and calls the appropriate endpoint
3. **Toast Notifications**: Provides user feedback on connection test results

## Error Handling

All endpoints include comprehensive error handling:

- **Network errors**: Timeout and connection failures
- **Authentication errors**: Invalid API keys
- **Rate limiting**: Built-in delays to avoid TMDB rate limits
- **Validation**: Request payload validation

## Security Considerations

- API keys are validated but not stored on the server
- Connections use timeout limits to prevent hanging requests
- All error messages are sanitized before being returned to the client

## Testing

To test the TMDB endpoints:

1. Ensure you have a valid TMDB API key from https://www.themoviedb.org/settings/api
2. Use the test endpoint to verify the key works
3. Check the genre endpoints to confirm API access is functioning

## Troubleshooting

**405 Method Not Allowed**: Ensure you're using POST for the test endpoint and GET for genre endpoints.

**401 Unauthorized**: Check that your TMDB API key is valid and hasn't expired.

**Connection Timeout**: Verify your network can access api.themoviedb.org and check firewall settings.