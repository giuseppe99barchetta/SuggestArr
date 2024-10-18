# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y cron supervisor && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Add the cron job
RUN echo "* * * * * cd /app && /usr/local/bin/python automate_process.py >> /var/log/cron.log 2>&1" > /etc/cron.d/automation-cron

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
