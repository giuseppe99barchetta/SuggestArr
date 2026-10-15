class RequestExpiryMixin:
    def track_seer_request(self, delivery_id, request_id, created_at, instance):
        ph = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        with self.get_connection() as conn:
            conn.cursor().execute(
                f'UPDATE pending_requests SET seer_request_id={ph}, seer_created_at={ph}, seer_instance={ph} '
                f'WHERE id={ph}', (request_id, created_at, instance, delivery_id),
            )
            conn.commit()

    def get_expiring_seer_requests(self, cutoff, instance):
        ph = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, seer_request_id, seer_created_at, tmdb_id, media_type FROM pending_requests '
                f"WHERE status='submitted' AND seer_instance={ph} AND seer_created_at < {ph} "
                'AND seer_request_id IS NOT NULL ORDER BY seer_created_at', (instance, cutoff),
            )
            return [dict(zip(('delivery_id', 'seer_request_id', 'seer_created_at', 'tmdb_id', 'media_type'), row))
                    for row in cursor.fetchall()]

    def add_request_expiry_log(self, item, action, reason, dry_run):
        ph = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        with self.get_connection() as conn:
            conn.cursor().execute(
                'INSERT INTO request_expiry_log '
                '(delivery_id, seer_request_id, tmdb_id, media_type, action, reason, dry_run) '
                f'VALUES ({",".join([ph] * 7)})',
                (item['delivery_id'], item['seer_request_id'], item['tmdb_id'], item['media_type'],
                 action, reason, int(dry_run)),
            )
            conn.commit()

    def get_request_expiry_log(self, limit=100):
        ph = '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, delivery_id, seer_request_id, tmdb_id, media_type, action, reason, dry_run, '
                f'created_at FROM request_expiry_log ORDER BY id DESC LIMIT {ph}', (limit,),
            )
            return [dict(zip(('id', 'delivery_id', 'seer_request_id', 'tmdb_id', 'media_type',
                              'action', 'reason', 'dry_run', 'created_at'), row)) for row in cursor.fetchall()]
