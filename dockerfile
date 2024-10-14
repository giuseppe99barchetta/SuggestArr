# Use an official Python runtime as a parent image
FROM python:3.13.0rc2-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install cron
RUN apt-get update && apt-get install -y cron

# Add the cron job
RUN echo "50 23 * * * cd /app && /usr/local/bin/python automate_process.py >> /var/log/cron.log 2>&1" > /etc/cron.d/automation-cron

# Give execution rights to the cron job
RUN chmod 0644 /etc/cron.d/automation-cron

# Apply cron job
RUN crontab /etc/cron.d/automation-cron

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

# Run the command on container startup
CMD ["sh", "-c", "cron && tail -f /var/log/cron.log"]
