# Stage 1: Build the client
FROM node:20 AS client-builder
WORKDIR /app/client
COPY client/package*.json ./ 
RUN npm install && npm cache clean --force
COPY client/ . 
RUN npm run build

# Stage 2: Create the final image
FROM python:3.13-slim AS prod

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl supervisor && \
    curl -sL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory for the api_service
WORKDIR /app/api_service

# Copy and install Python dependencies first (use cache efficiently)
COPY api_service/requirements.txt /app/api_service/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the client build files from the previous stage
COPY --from=client-builder /app/client/dist /app/static

# Copy the api_service source code
COPY api_service/ /app/api_service/

# Copy Supervisor configuration
COPY ../config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create log files for Gunicorn
RUN touch /var/log/gunicorn.log /var/log/gunicorn_error.log

# Expose the port used by Gunicorn
ARG SUGGESTARR_PORT=5000
EXPOSE ${SUGGESTARR_PORT}

# Start Supervisor to manage Gunicorn
ENV LOG_LEVEL=info
ENV SUGGESTARR_PORT=${SUGGESTARR_PORT}
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

# Dev stage
FROM prod AS dev
RUN pip install --no-cache-dir -r requirements.dev.txt
RUN python -m pytest .