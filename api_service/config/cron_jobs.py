from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
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
    trigger = parse_cron_expression(cron_expression)
    logger.debug(f'Parsed cron trigger: {trigger}')
    scheduler.add_job(force_run_job, trigger=trigger, id=job_id)
    
    logger.debug(f"Cron job '{job_id}' set with expression: {cron_expression}")
    scheduler.start()
    logger.debug('Scheduler started')

def parse_cron_expression(cron_expression):
    """
    Function to decode the cron expression.
    Returns a CronTrigger compatible with APScheduler.
    Falls back to '0 0 * * *' if the expression is missing or malformed.

    Uses CronTrigger.from_crontab() to correctly handle '*' wildcards.
    Building a CronTrigger manually with day_of_week='*' causes APScheduler
    to apply OR logic between 'day' and 'day_of_week', making schedules like
    '0 0 1 * *' fire every day instead of only on the 1st of the month.
    """
    default_expression = '0 0 * * *'
    logger.debug(f'Parsing cron expression: {cron_expression}')

    expression = (cron_expression or '').strip()
    if len(expression.split()) != 5:
        logger.warning(
            f"Invalid cron expression '{cron_expression}' (expected 5 parts, got {len(expression.split())}). "
            f"Falling back to default: '{default_expression}'"
        )
        expression = default_expression

    try:
        trigger = CronTrigger.from_crontab(expression)
        logger.debug(f'Cron expression parsed to trigger: {trigger}')
        return trigger
    except Exception as e:
        logger.warning(
            f"Failed to parse cron expression '{expression}': {e}. "
            f"Falling back to default: '{default_expression}'"
        )
        return CronTrigger.from_crontab(default_expression)
