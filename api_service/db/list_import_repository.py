"""The latest one-time import per owner; independent of automation jobs."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from api_service.db.database_manager import DatabaseManager


class ListImportRepository:
    def __init__(self, db=None):
        self.db = db or DatabaseManager()
        self.ph = '?' if self.db.db_type == 'sqlite' else '%s'

    def get(self, owner_id, run_id=None):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = f'SELECT * FROM list_import_runs WHERE owner_id={self.ph}'
            params = [owner_id]
            if run_id:
                query += f' AND id={self.ph}'
                params.append(run_id)
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            return dict(zip([col[0] for col in cursor.description], row)) if row else None

    def reserve(self, owner_id, config):
        """A unique owner row and conditional update prevent overlapping imports."""
        run_id = uuid.uuid4().hex
        query = f'INSERT INTO list_import_runs(id,owner_id,config_json,status) VALUES({self.ph},{self.ph},{self.ph},\'idle\')'
        if self.db.db_type in ('mysql', 'mariadb'):
            query = query.replace('INSERT INTO', 'INSERT IGNORE INTO')
        else:
            query += ' ON CONFLICT (owner_id) DO NOTHING'
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (run_id, owner_id, json.dumps(config)))
            cursor.execute(f'UPDATE list_import_runs SET id={self.ph},config_json={self.ph},status=\'queued\','
                           'scan_offset=0,scanned_count=0,requested_count=0,last_error=NULL,'
                           'lease_token=NULL,lease_until=NULL,updated_at=CURRENT_TIMESTAMP '
                           f"WHERE owner_id={self.ph} AND status IN ('idle','completed','failed')",
                           (run_id, json.dumps(config), owner_id))
            reserved = cursor.rowcount == 1
            conn.commit()
        return run_id if reserved else None

    def claim(self, owner_id, run_id):
        token = uuid.uuid4().hex
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'UPDATE list_import_runs SET status=\'running\',lease_token={self.ph},'
                           f'lease_until={self.ph},last_error=NULL WHERE owner_id={self.ph} AND id={self.ph} '
                           f"AND (status IN ('queued','failed') OR (status='running' AND lease_until < {self.ph}))",
                           (token, now + timedelta(minutes=10), owner_id, run_id, now))
            claimed = cursor.rowcount == 1
            conn.commit()
        return token if claimed else None

    def update(self, run_id, token, offset, scanned, requested, status='running', error=None):
        until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'UPDATE list_import_runs SET scan_offset={self.ph},scanned_count={self.ph},'
                           f'requested_count={self.ph},status={self.ph},last_error={self.ph},lease_until={self.ph},'
                           f'lease_token={self.ph},updated_at=CURRENT_TIMESTAMP WHERE id={self.ph} AND lease_token={self.ph}',
                           (offset, scanned, requested, status, error, until,
                            token if status == 'running' else None, run_id, token))
            changed = cursor.rowcount == 1
            conn.commit()
        return changed


def public_import_state(run):
    if not run:
        return None
    state = {key: run[key] for key in ('id', 'status', 'scanned_count', 'requested_count', 'last_error')}
    config = json.loads(run['config_json'])
    state['list_url'] = config['filters']['list_url']
    state['list_provider'] = config['filters']['list_provider']
    until = run.get('lease_until')
    if isinstance(until, str):
        until = datetime.fromisoformat(until)
    if state['status'] == 'running' and until and until < datetime.now(timezone.utc).replace(tzinfo=None):
        state.update(status='interrupted', last_error='Import interrupted. Resume to continue from the last title checked.')
    updated = run.get('updated_at')
    if isinstance(updated, str):
        updated = datetime.fromisoformat(updated)
    if state['status'] == 'queued' and updated and updated < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1):
        state.update(status='interrupted', last_error='Import did not start. Resume to try again.')
    return state
