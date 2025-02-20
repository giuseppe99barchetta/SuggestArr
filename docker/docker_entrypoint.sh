#!/bin/sh
set -e

args="$@"

cd /app && exec uvicorn api_service.app:asgi_app $(eval echo "$args") 
