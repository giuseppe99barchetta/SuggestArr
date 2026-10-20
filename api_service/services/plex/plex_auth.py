from api_service.services.http import sync_client as requests


class PlexAuth:
    def __init__(self, client_id):
        self.client_id = client_id
        self.base_url = 'https://plex.tv/api/v2'
        self.headers = {
            'X-Plex-Product': 'SuggestArr',
            'X-Plex-Client-Identifier': self.client_id,
            "Accept": 'application/json'
        }

    def get_authentication_pin(self):
        """Generate a new authentication PIN."""
        response = requests.post(f"{self.base_url}/pins?strong=true", headers=self.headers)
        data = response.json()
        auth_url = f"https://app.plex.tv/auth#?clientID={self.client_id}&code={data['code']}"
        return data['id'], auth_url
    
    def check_authentication(self, pin_id):
        """Check whether the user has completed authentication."""
        response = requests.get(f"{self.base_url}/pins/{pin_id}", headers=self.headers)
        data = response.json()
        if 'authToken' in data:
            return data['authToken']
        return None
