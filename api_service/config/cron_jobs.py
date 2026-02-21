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
        logger.info('Cron job executed successfully')
    except Exception as e:
        logger.error(f'Error executing cron job: {e}')

# Function to start the cron job
def start_cron_job(env_vars, job_id='auto_content_fetcher'):
    logger.debug('Starting cron job setup')
    scheduler = BackgroundScheduler()
    
    # Remove old jobs if exist
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)
        logger.info(f"Removed old job with ID: {job_id}")

    cron_expression = env_vars.get('CRON_TIMES', '0 0 * * *')  # Use the value of CRON_TIME from the environment variable
    logger.debug(f'Cron expression from env_vars: {cron_expression}')

    # Add the job using the dynamic cron expression
    cron_params = parse_cron_expression(cron_expression)
    logger.debug(f'Parsed cron parameters: {cron_params}')
    scheduler.add_job(force_run_job, 'cron', id=job_id, **cron_params)
    
    logger.debug(f"Cron job '{job_id}' set with expression: {cron_expression}")
    scheduler.start()
    logger.debug('Scheduler started')

def parse_cron_expression(cron_expression):
    """
    Function to decode the cron expression.
    Returns a dictionary compatible with APScheduler.
    Falls back to '0 0 * * *' if the expression is missing or malformed.
    """
    default_expression = '0 0 * * *'
    logger.debug(f'Parsing cron expression: {cron_expression}')
    cron_parts = (cron_expression or '').split()

    if len(cron_parts) != 5:
        logger.warning(
            f"Invalid cron expression '{cron_expression}' (expected 5 parts, got {len(cron_parts)}). "
            f"Falling back to default: '{default_expression}'"
        )
        cron_parts = default_expression.split()

    # Return the dictionary for APScheduler
    cron_params = {
        'minute': cron_parts[0],
        'hour': cron_parts[1],
        'day': cron_parts[2],
        'month': cron_parts[3],
        'day_of_week': cron_parts[4],
    }
    logger.debug(f'Cron expression parsed to: {cron_params}')
    return cron_params
