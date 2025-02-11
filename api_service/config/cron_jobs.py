from apscheduler.schedulers.background import BackgroundScheduler
from api_service.config.logger_manager import LoggerManager
import requests

# Logging configuration
logger = LoggerManager().get_logger("CronJobs")

# Function to be executed periodically
def force_run_job():
    try:
        logger.info('Cron job started')
        requests.post('http://localhost:5000/api/automation/force_run')
    except Exception as e:
        logger.error(f'Error executing cron job: {e}')

# Function to start the cron job
def start_cron_job(env_vars, job_id = 'auto_content_fetcher'):
    scheduler = BackgroundScheduler()
    
    # Remove old jobs if exist
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)
        logger.info(f"Removed old job with ID: {job_id}")

    cron_expression = env_vars.get('CRON_TIMES', '0 0 * * *')  # Use the value of CRON_TIME from the environment variable

    # Add the job using the dynamic cron expression
    scheduler.add_job(force_run_job, 'cron', id=job_id, **parse_cron_expression(cron_expression))
    
    logger.info(f"Cron job '{job_id}' set with expression: {cron_expression}")
    scheduler.start()

def parse_cron_expression(cron_expression):
    """
    Function to decode the cron expression.
    Returns a dictionary compatible with APScheduler.
    """
    cron_parts = cron_expression.split()

    # Return the dictionary for APScheduler
    return {
        'minute': cron_parts[0],
        'hour': cron_parts[1],
        'day': cron_parts[2],
        'month': cron_parts[3],
        'day_of_week': cron_parts[4],
    }
