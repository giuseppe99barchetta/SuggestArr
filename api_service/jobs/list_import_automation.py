"""Import public lists using the existing quality filters and Seer delivery path."""
import hashlib
import json
from contextlib import AsyncExitStack

from api_service.jobs.discover_automation import ExecutionResult
from api_service.jobs.trakt_recommendations_automation import TraktRecommendationsAutomation
from api_service.services.public_lists import PublicListError, build_list_client, normalize_list_item, parse_list_url


def validate_list_job(data):
    filters = data.get('filters')
    if not isinstance(filters, dict):
        raise PublicListError('List filters must be an object.')
    parse_list_url(filters.get('list_provider'), filters.get('list_url'))
    try:
        limit = data.get('max_results', 20)
        if isinstance(limit, bool) or int(limit) != float(limit) or not 1 <= int(limit) <= 1000:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise PublicListError('Maximum new requests must be between 1 and 1000.') from None
    data['max_results'] = int(limit)
    data['user_ids'] = []
    data['prevent_suggestions_if_unwatched'] = False


class ListImportAutomation(TraktRecommendationsAutomation):
    """Share client initialization and quality filtering, replacing the candidate source."""
    JOB_TYPE = 'list_import'
    PAGE_SIZE = 100
    SCAN_LIMIT = 1000

    async def _initialize_components(self, dry_run=False):
        validate_list_job(self.job_data)
        try:
            await super()._initialize_components(dry_run=dry_run)
        except Exception:
            await self._close_clients()
            raise

    async def _close_clients(self):
        for client in (self.seer_client, self.tmdb_client, self.trakt_client):
            if client:
                await client.close()
        if self.tmdb_client and self.tmdb_client.omdb_client:
            await self.tmdb_client.omdb_client.close()

    def _build_trakt_client(self):
        # The shared initialization owns this candidate-source client's lifetime.
        return build_list_client(self.job_data['filters'], self.env_vars)

    async def _fetch_tmdb_details(self, tmdb_id, media_type):
        # Keep the cursor at this candidate on transient TMDb failures.
        return await super()._fetch_tmdb_details(tmdb_id, media_type, raise_on_error=True)

    async def run(self, dry_run=False, execution_id=None):
        validate_list_job(self.job_data)
        original = self.repository.get_job(self.job_id)
        source_key = hashlib.sha256(json.dumps({
            'filters': original['filters'], 'media_type': original['media_type'],
        }, sort_keys=True).encode()).hexdigest()
        token = None
        offset = self.repository.list_scan_offset(self.job_id, source_key)
        count = scanned = 0
        preview = [] if dry_run else None
        exec_id = None if dry_run else (execution_id or self.repository.log_execution_start(self.job_id))
        self.seer_client.queue_context['execution_id'] = exec_id
        try:
            async with AsyncExitStack() as stack:
                for client in (self.seer_client, self.tmdb_client, self.tmdb_client.omdb_client, self.trakt_client):
                    if client:
                        await stack.enter_async_context(client)
                await self.trakt_client.public_list_info(self.job_data['filters']['list_url'])
                if not dry_run:
                    token = self.repository.claim_list_scan(self.job_id, source_key)
                    if not token:
                        raise PublicListError('This list job is already running. Try again later.')
                    offset = self.repository.list_scan_offset(self.job_id, source_key)
                seen = set()
                while scanned < self.SCAN_LIMIT and count < self.job_data['max_results']:
                    page, more = await self.trakt_client.public_list_page(
                        self.job_data['filters']['list_url'], offset, self.PAGE_SIZE)
                    consumed = 0
                    for raw in page:
                        if scanned >= self.SCAN_LIMIT or count >= self.job_data['max_results']:
                            break
                        if token and not self.repository.checkpoint_list_scan(self.job_id, token, offset):
                            raise PublicListError('List job lease expired. Try again later.')
                        item = normalize_list_item(raw)
                        if item and (self.job_data['media_type'] in ('both', item['media_type'])):
                            key = (item['media_type'], item['tmdb_id'])
                            if key not in seen:
                                seen.add(key)
                                if await self._candidate_available(item):
                                    enriched = await self._enrich_and_filter_item(item)
                                    if enriched:
                                        if dry_run:
                                            preview.append(self._format_dry_run_item(item['media_type'], enriched))
                                            count += 1
                                        elif await self.seer_client.request_media(item['media_type'], enriched,
                                                source={'id': 'list_import'}, user=None):
                                            count += 1
                        elif not item:
                            self.logger.debug('Skipping list item: unsupported type or missing valid TMDb ID.')
                        scanned += 1
                        consumed += 1
                        offset += 1
                        if token and not self.repository.checkpoint_list_scan(
                                self.job_id, token, offset):
                            raise PublicListError('List job lease expired. Try again later.')
                    # Only reset after consuming the complete final page.
                    if not page or (not more and consumed == len(page)):
                        offset = 0
                        break
                if not dry_run:
                    self.repository.log_execution_end(exec_id, 'completed', results_count=scanned, requested_count=count)
                if self.job_data.get('_replacement_for') is not None and not count and offset:
                    return ExecutionResult(False, scanned, count, error_message='List scan will continue on the next replacement check.')
                return ExecutionResult(True, scanned, count, dry_run_items=preview)
        except Exception as exc:
            message = str(exc) if isinstance(exc, PublicListError) else 'List import failed. Check the server logs.'
            self.logger.error('List import job %s failed (%s).', self.job_id, type(exc).__name__)
            if not dry_run:
                self.repository.log_execution_end(exec_id, 'failed', results_count=scanned,
                                                  requested_count=count, error_message=message)
            return ExecutionResult(False, scanned, count, error_message=message, dry_run_items=preview)
        finally:
            if token:
                self.repository.checkpoint_list_scan(self.job_id, token, offset, release=True)

    async def _candidate_available(self, item):
        kind, tmdb_id = item['media_type'], item['tmdb_id']
        if self.db_manager.check_request_exists(kind, tmdb_id):
            return False
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            ph = '?' if self.db_manager.db_type == 'sqlite' else '%s'
            cursor.execute(f'SELECT 1 FROM pending_requests WHERE tmdb_id={ph} AND media_type={ph}', (tmdb_id, kind))
            if cursor.fetchone():
                return False
        if self.db_manager.is_suggestion_blacklisted(tmdb_id, kind):
            return False
        if self.db_manager._automated_submission_skip_reason(self.job_id, self.job_data.get('owner_id'), tmdb_id, kind, None):
            return False
        return not (await self.seer_client.check_already_downloaded(int(tmdb_id), kind, self.local_content)
                    or await self.seer_client.check_already_requested(int(tmdb_id), kind))


async def execute_list_import_job(job_id, overrides=None, execution_id=None):
    try:
        automation = await ListImportAutomation.create(job_id, overrides=overrides)
        return await automation.run(execution_id=execution_id)
    except Exception as exc:
        message = str(exc) if isinstance(exc, PublicListError) else 'Could not initialize list import.'
        return ExecutionResult(False, 0, 0, error_message=message)
