"""Remote decisions and one durable replacement slot per rejected delivery."""


class RequestReplacementMixin:
    def get_seer_requests_to_check(self, instance, limit=50):
        ph = '?' if self.db_type == 'sqlite' else '%s'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT p.id AS delivery_id,p.seer_request_id,p.seer_created_at,p.tmdb_id,p.media_type '
                'FROM pending_requests p LEFT JOIN request_replacements r ON r.delivery_id=p.id '
                f"WHERE p.status='submitted' AND p.seer_instance={ph} AND p.seer_request_id IS NOT NULL "
                'AND p.job_id IS NOT NULL AND (r.remote_status IS NULL OR r.remote_status=1) '
                f'ORDER BY CASE WHEN r.checked_at IS NULL THEN 0 ELSE 1 END,r.checked_at,p.id LIMIT {ph}', (instance, limit),
            )
            return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    def record_seer_request_check(self, delivery_id, remote_status, status, reason):
        ph = '?' if self.db_type == 'sqlite' else '%s'
        query = ('INSERT INTO request_replacements(delivery_id,remote_status,status,reason) '
                 f'VALUES ({ph},{ph},{ph},{ph}) ')
        if self.db_type in ('mysql', 'mariadb'):
            query += ('ON DUPLICATE KEY UPDATE status=IF(remote_status=1,VALUES(status),status),'
                      'reason=IF(remote_status=1,VALUES(reason),reason),'
                      'remote_status=IF(remote_status=1,VALUES(remote_status),remote_status),checked_at=CURRENT_TIMESTAMP')
        else:
            query += ('ON CONFLICT(delivery_id) DO UPDATE SET remote_status=excluded.remote_status,'
                      'status=excluded.status,reason=excluded.reason,checked_at=CURRENT_TIMESTAMP '
                      'WHERE request_replacements.remote_status=1')
        with self.get_connection() as conn:
            conn.cursor().execute(query, (delivery_id, remote_status, status, reason))
            conn.commit()

    def was_automatically_declined(self, delivery_id):
        ph = '?' if self.db_type == 'sqlite' else '%s'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'SELECT 1 FROM request_expiry_log WHERE delivery_id={ph} '
                "AND action IN ('decline_requested','declined') AND dry_run=0 LIMIT 1", (delivery_id,),
            )
            return cursor.fetchone() is not None

    def get_pending_request_replacements(self, instance, limit=10):
        ph = '?' if self.db_type == 'sqlite' else '%s'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT p.id AS delivery_id,p.job_id,p.owner_id,p.user_id,p.media_type,j.max_results '
                'FROM request_replacements r JOIN pending_requests p ON p.id=r.delivery_id '
                'LEFT JOIN discover_jobs j ON j.id=p.job_id '
                f"WHERE r.status='pending' AND p.seer_instance={ph} "
                f'ORDER BY r.checked_at,p.id LIMIT {ph}', (instance, limit),
            )
            return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    def finish_request_replacement(self, delivery_id, status, reason):
        ph = '?' if self.db_type == 'sqlite' else '%s'
        with self.get_connection() as conn:
            conn.cursor().execute(
                f'UPDATE request_replacements SET status={ph},reason={ph},checked_at=CURRENT_TIMESTAMP '
                f"WHERE delivery_id={ph} AND status='pending'", (status, reason, delivery_id),
            )
            conn.commit()

    def get_request_replacement_log(self, limit=100):
        ph = '?' if self.db_type == 'sqlite' else '%s'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT r.*,p.seer_request_id,p.tmdb_id,p.media_type FROM request_replacements r '
                'JOIN pending_requests p ON p.id=r.delivery_id '
                f"WHERE r.status<>'observing' ORDER BY r.checked_at DESC,r.delivery_id DESC LIMIT {ph}", (limit,),
            )
            return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
