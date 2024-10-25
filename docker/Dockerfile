# Stage 1: Build the frontend
FROM node:20 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Create the final image
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl cron supervisor && \
    curl -sL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory for the backend
WORKDIR /app/backend

# Copy and install Python dependencies
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the frontend build files from the previous stage
COPY --from=frontend-builder /app/frontend/dist /app/static

# Copy the backend source code
COPY backend/ /app/backend/

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

# Start Supervisor to manage Gunicorn and cron
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
