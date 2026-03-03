import requests
import json

app_url = 'http://127.0.0.1:5000'

payload = {
    'SEER_API_URL': 'http://127.0.0.1:5055',
    'SEER_TOKEN': 'test_token'
}

response = requests.post(f"{app_url}/api/seer/test", json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

response = requests.post(f"{app_url}/api/seer/get_users", json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
