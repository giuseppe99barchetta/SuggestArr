"""
This script loads environment variables for connecting to the TMDb, Jellyfin, and Jellyseer APIs.
It uses the dotenv library to load variables from a .env file and validates their presence.
"""
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

# Leggi le variabili dall'ambiente
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
JELLYFIN_API_URL = os.getenv('JELLYFIN_API_URL')
JELLYFIN_TOKEN = os.getenv('JELLYFIN_TOKEN')
USER_ID = os.getenv('USER_ID')
JELLYSEER_API_URL = os.getenv('JELLYSEER_API_URL')
JELLYSEER_TOKEN = os.getenv('JELLYSEER_TOKEN')
JELLYSEER_USER = os.getenv('JELLYSEER_USER')
JELLYSEER_PASSWORD = os.getenv('JELLYSEER_PASSWORD')
TVDB_API_KEY = os.getenv('TVDB_API_KEY')
