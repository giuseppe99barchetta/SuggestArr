"""
Repository for discover jobs and job execution history.
Provides CRUD operations for the discover_jobs and job_execution_history tables.
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager


class JobRepository:
    """Repository for managing discover jobs and their execution history."""

    def __init__(self):
        """Initialize the job repository."""
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.db = DatabaseManager()

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Retrieve all jobs from the database.

        Returns:
            List of job dictionaries with parsed filters.
        """
        self.logger.debug("Retrieving all jobs")

        query = """
            SELECT id, name, job_type, enabled, media_type, filters, schedule_type,
                   schedule_value, max_results, user_ids, is_system, created_at, updated_at
            FROM discover_jobs
            ORDER BY is_system DESC, created_at DESC
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            jobs = []
            for row in rows:
                job = self._row_to_job_dict(row)
                jobs.append(job)

            return jobs

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single job by ID.

        Args:
            job_id: The ID of the job to retrieve.

        Returns:
            Job dictionary or None if not found.
        """
        self.logger.debug(f"Retrieving job with ID: {job_id}")

        query = """
            SELECT id, name, job_type, enabled, media_type, filters, schedule_type,
                   schedule_value, max_results, user_ids, is_system, created_at, updated_at
            FROM discover_jobs
            WHERE id = ?
        """
        params = (job_id,)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if self.db.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s")

            cursor.execute(query, params)
            row = cursor.fetchone()

            if row:
                return self._row_to_job_dict(row)
            return None

    def get_enabled_jobs(self) -> List[Dict[str, Any]]:
        """
        Retrieve all enabled jobs.

        Returns:
            List of enabled job dictionaries.
        """
        self.logger.debug("Retrieving all enabled jobs")

        query = """
            SELECT id, name, job_type, enabled, media_type, filters, schedule_type,
                   schedule_value, max_results, user_ids, is_system, created_at, updated_at
            FROM discover_jobs
            WHERE enabled = 1
            ORDER BY is_system DESC, created_at DESC
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            jobs = []
            for row in rows:
                job = self._row_to_job_dict(row)
                jobs.append(job)

            return jobs

    def create_job(self, job_data: Dict[str, Any]) -> int:
        """
        Create a new job (discover or recommendation).

        Args:
            job_data: Dictionary containing job details:
                - name: Job name
                - job_type: 'discover' or 'recommendation' (default: 'discover')
                - media_type: 'movie', 'tv', or 'both'
                - filters: Dictionary of TMDb filters
                - schedule_type: 'preset' or 'cron'
                - schedule_value: Schedule value (e.g., 'daily', '0 0 * * *')
                - max_results: Maximum results to fetch (optional, default 20)
                - user_ids: List of user IDs to monitor (for recommendation jobs)
                - enabled: Whether job is enabled (optional, default True)

        Returns:
            ID of the created job.
        """
        self.logger.debug(f"Creating new job: {job_data.get('name')} (type: {job_data.get('job_type', 'discover')})")

        filters_json = json.dumps(job_data.get('filters', {}))
        enabled = 1 if job_data.get('enabled', True) else 0
        max_results = job_data.get('max_results', 20)
        job_type = job_data.get('job_type', 'discover')
        user_ids = json.dumps(job_data.get('user_ids', [])) if job_data.get('user_ids') else None
        is_system = 1 if job_data.get('is_system', False) else 0

        query = """
            INSERT INTO discover_jobs (name, job_type, enabled, media_type, filters,
                                       schedule_type, schedule_value, max_results, user_ids, is_system)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            job_data['name'],
            job_type,
            enabled,
            job_data['media_type'],
            filters_json,
            job_data['schedule_type'],
            job_data['schedule_value'],
            max_results,
            user_ids,
            is_system
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if self.db.db_type == 'mysql':
                query = query.replace("?", "%s")
            elif self.db.db_type == 'postgres':
                query = query.replace("?", "%s")
                query += " RETURNING id"

            cursor.execute(query, params)
            conn.commit()

            if self.db.db_type == 'postgres':
                result = cursor.fetchone()
                job_id = result[0]
            else:
                job_id = cursor.lastrowid

            self.logger.info(f"Created discover job with ID: {job_id}")
            return job_id

    def update_job(self, job_id: int, job_data: Dict[str, Any]) -> bool:
        """
        Update an existing discover job.

        Args:
            job_id: ID of the job to update.
            job_data: Dictionary of fields to update.

        Returns:
            True if job was updated, False if not found.
        """
        self.logger.debug(f"Updating discover job ID: {job_id}")

        # Build dynamic update query
        update_fields = []
        params = []

        if 'name' in job_data:
            update_fields.append("name = ?")
            params.append(job_data['name'])

        if 'enabled' in job_data:
            update_fields.append("enabled = ?")
            params.append(1 if job_data['enabled'] else 0)

        if 'media_type' in job_data:
            update_fields.append("media_type = ?")
            params.append(job_data['media_type'])

        if 'filters' in job_data:
            update_fields.append("filters = ?")
            params.append(json.dumps(job_data['filters']))

        if 'schedule_type' in job_data:
            update_fields.append("schedule_type = ?")
            params.append(job_data['schedule_type'])

        if 'schedule_value' in job_data:
            update_fields.append("schedule_value = ?")
            params.append(job_data['schedule_value'])

        if 'max_results' in job_data:
            update_fields.append("max_results = ?")
            params.append(job_data['max_results'])

        if 'job_type' in job_data:
            update_fields.append("job_type = ?")
            params.append(job_data['job_type'])

        if 'user_ids' in job_data:
            update_fields.append("user_ids = ?")
            params.append(json.dumps(job_data['user_ids']) if job_data['user_ids'] else None)

        if not update_fields:
            self.logger.warning("No fields to update for job ID: %d", job_id)
            return False

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(job_id)

        query = f"""
            UPDATE discover_jobs
            SET {', '.join(update_fields)}
            WHERE id = ?
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if self.db.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s")

            cursor.execute(query, tuple(params))
            conn.commit()

            updated = cursor.rowcount > 0
            if updated:
                self.logger.info(f"Updated discover job ID: {job_id}")
            else:
                self.logger.warning(f"No job found with ID: {job_id}")

            return updated

    def toggle_job(self, job_id: int, enabled: bool) -> bool:
        """
        Enable or disable a discover job.

        Args:
            job_id: ID of the job to toggle.
            enabled: True to enable, False to disable.

        Returns:
            True if job was updated, False if not found.
        """
        self.logger.debug(f"Toggling job ID {job_id} to enabled={enabled}")
        return self.update_job(job_id, {'enabled': enabled})

    def log_execution_start(self, job_id: int) -> int:
        """
        Log the start of a job execution.

        Args:
            job_id: ID of the job being executed.

        Returns:
            ID of the execution history record.
        """
        self.logger.debug(f"Logging execution start for job ID: {job_id}")

        query = """
            INSERT INTO job_execution_history (job_id, started_at, status)
            VALUES (?, ?, ?)
        """
        params = (job_id, datetime.now().isoformat(), 'running')

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if self.db.db_type == 'mysql':
                query = query.replace("?", "%s")
            elif self.db.db_type == 'postgres':
                query = query.replace("?", "%s")
                query += " RETURNING id"

            cursor.execute(query, params)
            conn.commit()

            if self.db.db_type == 'postgres':
                result = cursor.fetchone()
                exec_id = result[0]
            else:
                exec_id = cursor.lastrowid

            self.logger.debug(f"Created execution history record ID: {exec_id}")
            return exec_id

    def log_execution_end(
        self,
        exec_id: int,
        status: str,
        results_count: int = 0,
        requested_count: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log the end of a job execution.

        Args:
            exec_id: ID of the execution history record.
            status: Final status ('completed' or 'failed').
            results_count: Number of results found.
            requested_count: Number of items requested to Jellyseer/Overseer.
            error_message: Error message if failed.
        """
        self.logger.debug(f"Logging execution end for record ID: {exec_id}, status: {status}")

        query = """
            UPDATE job_execution_history
            SET finished_at = ?, status = ?, results_count = ?,
                requested_count = ?, error_message = ?
            WHERE id = ?
        """
        params = (
            datetime.now().isoformat(),
            status,
            results_count,
            requested_count,
            error_message,
            exec_id
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if self.db.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s")

            cursor.execute(query, params)
            conn.commit()

            self.logger.debug(f"Updated execution history record ID: {exec_id}")

    def get_job_history(self, job_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve execution history for a specific job.

        Args:
            job_id: ID of the job.
            limit: Maximum number of records to return.

        Returns:
            List of execution history dictionaries.
        """
        self.logger.debug(f"Retrieving history for job ID: {job_id}, limit: {limit}")

        query = """
            SELECT h.id, h.job_id, h.started_at, h.finished_at, h.status,
                   h.results_count, h.requested_count, h.error_message,
                   j.name as job_name
            FROM job_execution_history h
            JOIN discover_jobs j ON h.job_id = j.id
            WHERE h.job_id = ?
            ORDER BY h.started_at DESC
            LIMIT ?
        """
        params = (job_id, limit)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if self.db.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s")

            cursor.execute(query, params)
            rows = cursor.fetchall()

            history = []
            for row in rows:
                history.append(self._row_to_history_dict(row))

            return history

    def get_recent_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve recent execution history across all jobs.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of execution history dictionaries.
        """
        self.logger.debug(f"Retrieving recent history, limit: {limit}")

        query = """
            SELECT h.id, h.job_id, h.started_at, h.finished_at, h.status,
                   h.results_count, h.requested_count, h.error_message,
                   j.name as job_name
            FROM job_execution_history h
            JOIN discover_jobs j ON h.job_id = j.id
            ORDER BY h.started_at DESC
            LIMIT ?
        """
        params = (limit,)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if self.db.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s")

            cursor.execute(query, params)
            rows = cursor.fetchall()

            history = []
            for row in rows:
                history.append(self._row_to_history_dict(row))

            return history

    def _row_to_job_dict(self, row) -> Dict[str, Any]:
        """
        Convert a database row to a job dictionary.

        Args:
            row: Database row (tuple or Row object).

        Returns:
            Job dictionary with parsed filters.
        """
        # Handle both tuple and Row objects
        if hasattr(row, 'keys'):
            # Row object with column names
            data = dict(row)
        else:
            # Plain tuple - order matches SELECT query:
            # id, name, job_type, enabled, media_type, filters, schedule_type,
            # schedule_value, max_results, user_ids, is_system, created_at, updated_at
            data = {
                'id': row[0],
                'name': row[1],
                'job_type': row[2],
                'enabled': row[3],
                'media_type': row[4],
                'filters': row[5],
                'schedule_type': row[6],
                'schedule_value': row[7],
                'max_results': row[8],
                'user_ids': row[9],
                'is_system': row[10],
                'created_at': row[11],
                'updated_at': row[12]
            }

        # Parse filters JSON
        if isinstance(data.get('filters'), str):
            try:
                data['filters'] = json.loads(data['filters'])
            except json.JSONDecodeError:
                data['filters'] = {}

        # Parse user_ids JSON
        if isinstance(data.get('user_ids'), str):
            try:
                data['user_ids'] = json.loads(data['user_ids'])
            except json.JSONDecodeError:
                data['user_ids'] = []
        elif data.get('user_ids') is None:
            data['user_ids'] = []

        # Convert enabled to boolean
        data['enabled'] = bool(data.get('enabled', 0))

        # Convert is_system to boolean
        data['is_system'] = bool(data.get('is_system', 0))

        # Default job_type to 'discover' if not set
        if not data.get('job_type'):
            data['job_type'] = 'discover'

        return data

    def get_system_job(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve the system job (created from YAML config).

        Returns:
            System job dictionary or None if not found.
        """
        self.logger.debug("Retrieving system job")

        query = """
            SELECT id, name, job_type, enabled, media_type, filters, schedule_type,
                   schedule_value, max_results, user_ids, is_system, created_at, updated_at
            FROM discover_jobs
            WHERE is_system = 1
            LIMIT 1
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()

            if row:
                return self._row_to_job_dict(row)
            return None

    def upsert_system_job(self, job_data: Dict[str, Any]) -> int:
        """
        Create or update the system job from YAML config.
        If a system job exists, update it. Otherwise, create it.

        Args:
            job_data: Dictionary containing job details.

        Returns:
            ID of the system job.
        """
        self.logger.debug("Upserting system job from config")

        existing = self.get_system_job()

        if existing:
            # Update existing system job
            job_id = existing['id']
            self.update_job(job_id, job_data)
            self.logger.info(f"Updated system job ID: {job_id}")
            return job_id
        else:
            # Create new system job
            job_data['is_system'] = True
            job_id = self.create_job(job_data)
            self.logger.info(f"Created system job ID: {job_id}")
            return job_id

    def delete_job(self, job_id: int, allow_system: bool = False) -> bool:
        """
        Delete a discover job and its execution history.

        Args:
            job_id: ID of the job to delete.
            allow_system: If True, allows deletion of system jobs.

        Returns:
            True if job was deleted, False if not found or protected.
        """
        self.logger.debug(f"Deleting discover job ID: {job_id}")

        # Check if this is a system job
        if not allow_system:
            job = self.get_job(job_id)
            if job and job.get('is_system'):
                self.logger.warning(f"Cannot delete system job ID: {job_id}")
                return False

        query = "DELETE FROM discover_jobs WHERE id = ?"
        params = (job_id,)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if self.db.db_type in ['mysql', 'postgres']:
                query = query.replace("?", "%s")

            cursor.execute(query, params)
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                self.logger.info(f"Deleted discover job ID: {job_id}")
            else:
                self.logger.warning(f"No job found with ID: {job_id}")

            return deleted

    def _row_to_history_dict(self, row) -> Dict[str, Any]:
        """
        Convert a database row to a history dictionary.

        Args:
            row: Database row (tuple or Row object).

        Returns:
            History dictionary.
        """
        # Handle both tuple and Row objects
        if hasattr(row, 'keys'):
            return dict(row)
        else:
            return {
                'id': row[0],
                'job_id': row[1],
                'started_at': row[2],
                'finished_at': row[3],
                'status': row[4],
                'results_count': row[5],
                'requested_count': row[6],
                'error_message': row[7],
                'job_name': row[8] if len(row) > 8 else None
            }
