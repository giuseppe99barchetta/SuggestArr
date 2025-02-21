# Stage 1: Build the client
FROM node:22 AS client-builder
WORKDIR /app/client
COPY client/package*.json ./ 
RUN npm install && npm cache clean --force
COPY client/ . 
RUN npm run build

# Stage 2: Create the final image
FROM python:3.13-alpine AS prod

# Install tzdata for timezone support
RUN apk add --no-cache tzdata

# Set the timezone
ENV TZ=UTC

# Set the working directory for the api_service
WORKDIR /app/api_service

# Set PUID and PGID (with default values)
ENV PUID=2000
ENV PGID=2000

# Create a user and group with the provided PUID/PGID
RUN addgroup -g ${PGID} appgroup && \
    adduser -D -u ${PUID} -G appgroup appuser && \
    chown -R appuser:appgroup /app

# Switch to root to create log files
USER root

# Copy and install Python dependencies first (use cache efficiently)
COPY api_service/requirements.txt /app/api_service/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the client build files from the previous stage
COPY --from=client-builder /app/client/dist /app/static

# Copy the api_service source code
COPY api_service/ /app/api_service/

# Copy docker entrypoint script
COPY docker/docker_entrypoint.sh /app/

# Add executable permission
RUN chmod +x /app/docker_entrypoint.sh

# Create log files for Gunicorn
RUN touch /var/log/gunicorn.log /var/log/gunicorn_error.log

# Switch back to the appuser
USER appuser

# Expose the port used by Gunicorn
EXPOSE 5000

# Start Supervisor to manage Gunicorn
ENV LOG_LEVEL=info
ENTRYPOINT ["/app/docker_entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "5000", "--log-level", "info"]
