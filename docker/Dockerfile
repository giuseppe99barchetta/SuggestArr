# Stage 1: Build the client
FROM node:20 AS client-builder
WORKDIR /app/client
COPY client/package*.json ./
RUN npm install
COPY client/ .
RUN npm run build

# Stage 2: Create the final image
FROM python:3.13-slim AS prod

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl cron supervisor && \
    curl -sL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory for the api_service
WORKDIR /app/api_service

# Use environment variables for PUID and PGID
ARG PUID
ARG PGID

# Create a group and user with the specified PUID and PGID
RUN groupadd -g ${PGID} appgroup && \
    useradd -u ${PUID} -g appgroup -m appuser

# Copy and install Python dependencies
COPY api_service/requirements.txt /app/api_service/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the client build files from the previous stage
COPY --from=client-builder /app/client/dist /app/static

# Copy the api_service source code
COPY api_service/ /app/api_service/

# Copy Supervisor configuration
COPY ../config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Add and configure the cron job
RUN echo "0 0 * * * curl -X POST http://localhost:5000/api/automation/force_run >> /var/log/cron.log 2>&1" > /etc/cron.d/automation-cron && \
    chmod 0644 /etc/cron.d/automation-cron && \
    crontab /etc/cron.d/automation-cron

# Create log files for cron and Gunicorn
RUN touch /var/log/cron.log /var/log/gunicorn.log /var/log/gunicorn_error.log

# Expose the port used by Gunicorn
EXPOSE 5000

# Switch to the created user
USER appuser

# Start Supervisor to manage Gunicorn and cron
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

FROM prod AS dev
RUN pip install --no-cache-dir -r requirements.dev.txt
RUN python -m pytest .