"""
Job Manager for automation jobs.
Singleton that manages APScheduler jobs for both discover and recommendation automation.
"""
import asyncio
import threading
from typing import Any, Callable, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api_service.config.logger_manager import LoggerManager
from api_service.db.job_repository import JobRepository


class JobManager:
    """
    Singleton class that manages APScheduler jobs for automation.
    Handles scheduling, unscheduling, and running jobs.
    Supports both 'discover' and 'recommendation' job types.
    """

    _instance: Optional['JobManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Create or return the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the job manager."""
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.scheduler = BackgroundScheduler()
        self.repository = JobRepository()
        # Executors for different job types
        self._job_executors: Dict[str, Callable] = {}
        self._initialized = True
        self.logger.info("JobManager initialized")

    @classmethod
    def get_instance(cls) -> 'JobManager':
        """
        Get the singleton instance of JobManager.

        Returns:
            The JobManager singleton instance.
        """
        return cls()

    def set_job_executor(self, executor: Callable, job_type: str = 'discover') -> None:
        """
        Set the function to be called when a job of the specified type is executed.

        Args:
            executor: Async function that takes job_id as argument.
            job_type: Type of job this executor handles ('discover' or 'recommendation').
        """
        self._job_executors[job_type] = executor
        self.logger.debug(f"Job executor set for type: {job_type}")

    def start(self) -> None:
        """Start the scheduler if not already running."""
        if not self.scheduler.running:
            self.scheduler.start()
            self.logger.info("Job scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self.logger.info("Job scheduler stopped")

    def sync_jobs_from_db(self) -> None:
        """
        Synchronize jobs from the database to the scheduler.
        Removes orphan jobs and adds/updates jobs from DB.
        """
        self.logger.info("Synchronizing jobs from database")

        # Get all enabled jobs from database
        db_jobs = self.repository.get_enabled_jobs()
        db_job_ids = {f"discover_job_{job['id']}" for job in db_jobs}

        # Remove orphan jobs from scheduler
        for job in self.scheduler.get_jobs():
            if job.id.startswith('discover_job_') and job.id not in db_job_ids:
                self.logger.info(f"Removing orphan job: {job.id}")
                self.scheduler.remove_job(job.id)

        # Add/update jobs from database
        for job in db_jobs:
            self.schedule_job(job)

        self.logger.info(f"Synchronized {len(db_jobs)} jobs")

    def schedule_job(self, job: Dict[str, Any]) -> None:
        """
        Schedule or update a discover job.

        Args:
            job: Job dictionary from database.
        """
        job_id = f"discover_job_{job['id']}"
        self.logger.debug(f"Scheduling job: {job_id} ({job['name']})")

        # Remove existing job if present
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)

        # Parse schedule
        trigger = self._create_trigger(job['schedule_type'], job['schedule_value'])
        if not trigger:
            self.logger.error(f"Invalid schedule for job {job_id}: {job['schedule_value']}")
            return

        # Add job to scheduler
        self.scheduler.add_job(
            self._execute_job,
            trigger=trigger,
            id=job_id,
            name=job['name'],
            args=[job['id']],
            replace_existing=True
        )

        self.logger.info(f"Scheduled job: {job['name']} with schedule: {job['schedule_value']}")

    def unschedule_job(self, job_id: int) -> None:
        """
        Remove a job from the scheduler.

        Args:
            job_id: Database ID of the job.
        """
        scheduler_job_id = f"discover_job_{job_id}"
        existing = self.scheduler.get_job(scheduler_job_id)

        if existing:
            self.scheduler.remove_job(scheduler_job_id)
            self.logger.info(f"Unscheduled job: {scheduler_job_id}")
        else:
            self.logger.debug(f"Job not found in scheduler: {scheduler_job_id}")

    def run_job_now(self, job_id: int) -> None:
        """
        Execute a job immediately (not via scheduler).

        Args:
            job_id: Database ID of the job to run.
        """
        self.logger.info(f"Running job {job_id} immediately")
        self._execute_job(job_id)

    def _execute_job(self, job_id: int) -> None:
        """
        Internal method to execute a job.
        Creates a new event loop for async execution.
        Determines job type and calls appropriate executor.

        Args:
            job_id: Database ID of the job.
        """
        # Get job data to determine type
        job_data = self.repository.get_job(job_id)
        if not job_data:
            self.logger.error(f"Job not found: {job_id}")
            return

        job_type = job_data.get('job_type', 'discover')
        self.logger.info(f"Executing {job_type} job: {job_id} ({job_data['name']})")

        # Get the executor for this job type
        executor = self._job_executors.get(job_type)
        if executor is None:
            self.logger.error(f"No executor set for job type: {job_type}")
            return

        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(executor(job_id))
            finally:
                loop.close()

            self.logger.info(f"Job {job_id} execution completed")
        except Exception as e:
            self.logger.error(f"Job {job_id} execution failed: {str(e)}")

    def _create_trigger(self, schedule_type: str, schedule_value: str) -> Optional[CronTrigger]:
        """
        Create a CronTrigger from schedule configuration.

        Args:
            schedule_type: 'preset' or 'cron'.
            schedule_value: Preset name or cron expression.

        Returns:
            CronTrigger instance or None if invalid.
        """
        if schedule_type == 'preset':
            return self._preset_to_trigger(schedule_value)
        elif schedule_type == 'cron':
            return self._cron_to_trigger(schedule_value)
        else:
            self.logger.error(f"Unknown schedule type: {schedule_type}")
            return None

    def _preset_to_trigger(self, preset: str) -> Optional[CronTrigger]:
        """
        Convert a preset schedule to a CronTrigger.

        Args:
            preset: Preset name (daily, weekly, every_12h, every_6h).

        Returns:
            CronTrigger instance or None if invalid.
        """
        presets = {
            'daily': CronTrigger(hour=0, minute=0),
            'weekly': CronTrigger(day_of_week='mon', hour=0, minute=0),
            'every_12h': CronTrigger(hour='*/12', minute=0),
            'every_6h': CronTrigger(hour='*/6', minute=0),
            'every_hour': CronTrigger(minute=0),
        }

        trigger = presets.get(preset.lower())
        if not trigger:
            self.logger.error(f"Unknown preset: {preset}")

        return trigger

    def _cron_to_trigger(self, cron_expr: str) -> Optional[CronTrigger]:
        """
        Convert a cron expression to a CronTrigger.

        Args:
            cron_expr: Standard cron expression (minute hour day month day_of_week).

        Returns:
            CronTrigger instance or None if invalid.
        """
        try:
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                self.logger.error(f"Invalid cron expression (expected 5 parts): {cron_expr}")
                return None

            return CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )
        except Exception as e:
            self.logger.error(f"Error parsing cron expression '{cron_expr}': {str(e)}")
            return None

    def get_scheduled_jobs(self) -> list:
        """
        Get list of currently scheduled jobs.

        Returns:
            List of job info dictionaries.
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            if job.id.startswith('discover_job_'):
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                })
        return jobs
