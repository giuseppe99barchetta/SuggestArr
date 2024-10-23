import requests


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
        """Genera un nuovo pin di autenticazione."""
        response = requests.post(f"{self.base_url}/pins?strong=true", headers=self.headers)
        data = response.json()
        auth_url = f"https://app.plex.tv/auth#?clientID={self.client_id}&code={data['code']}"
        return data['id'], auth_url
    
    def check_authentication(self, pin_id):
        """Verifica se l'utente ha completato l'autenticazione."""
        response = requests.get(f"{self.base_url}/pins/{pin_id}", headers=self.headers)
        data = response.json()
        if 'authToken' in data:
            print(data)
            return data['authToken']
        return None