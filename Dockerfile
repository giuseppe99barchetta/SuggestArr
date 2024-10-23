# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl cron supervisor && \
    curl -sL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install frontend dependencies
WORKDIR /app/suggestarr-frontend
RUN npm install
RUN npm run build

# Copy the built frontend files to a static directory in the backend
RUN mkdir -p /app/static
RUN cp -R /app/suggestarr-frontend/dist/* /app/static/

# Return to the /app directory for backend work
WORKDIR /app

RUN touch .env

# Copy the Supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Add the cron job
RUN echo "0 0 * * * curl -X POST http://localhost:5000/api/automation/force_run >> /var/log/cron.log 2>&1" > /etc/cron.d/automation-cron

# Give execution rights to the cron job
RUN chmod 0644 /etc/cron.d/automation-cron

# Apply the cron job
RUN crontab /etc/cron.d/automation-cron

# Create log files for cron and Gunicorn
RUN touch /var/log/cron.log /var/log/gunicorn.log /var/log/gunicorn_error.log

# Expose the port Gunicorn is running on
EXPOSE 5000

# Start Supervisor to manage Gunicorn and cron
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
