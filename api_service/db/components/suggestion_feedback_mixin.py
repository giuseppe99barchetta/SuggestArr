"""Per-user feedback for queued suggestions.

Feedback intentionally remains separate from the global suggestion blacklist: it is
scoped to the authenticated SuggestArr user and the linked media profile.
"""

import json


class SuggestionFeedbackMixin:
    NEGATIVE_FEEDBACK = {'not_interested', 'already_seen', 'too_similar'}

    def _feedback_placeholder(self):
        return '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    @staticmethod
    def _feedback_media_user_id(value):
        return '' if value is None else str(value)

    def _feedback_suggestion(self, cursor, suggestion_id, owner_id, media_user_ids=None):
        ph = self._feedback_placeholder()
        query = f"SELECT tmdb_id, media_type, user_id, payload FROM pending_requests WHERE id={ph}"
        params = [suggestion_id]
        if owner_id is not None:
            query += f" AND owner_id={ph}"
            params.append(owner_id)
        cursor.execute(query, tuple(params))
        row = cursor.fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row[3] or '{}')
        except (TypeError, json.JSONDecodeError):
            payload = {}
        media_user_id = self._feedback_media_user_id(payload.get('_user_id', row[2]))
        if media_user_ids is not None and media_user_id not in {str(value) for value in media_user_ids}:
            return None
        return str(row[0]), row[1], media_user_id

    def set_suggestion_feedback(self, suggestion_id, owner_id, user_id, feedback,
                                reason_type=None, reason_text=None, media_user_ids=None):
        """Store one user's feedback for a suggestion they are allowed to view."""
        ph = self._feedback_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            suggestion = self._feedback_suggestion(cursor, suggestion_id, owner_id, media_user_ids)
            if not suggestion:
                return None
            tmdb_id, media_type, media_user_id = suggestion
            if self.db_type == 'sqlite':
                query = f"""
                    INSERT INTO suggestion_feedback
                        (user_id, media_user_id, tmdb_id, media_type, feedback, reason_type, reason_text)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                    ON CONFLICT(user_id, media_user_id, tmdb_id, media_type) DO UPDATE SET
                        feedback=excluded.feedback, reason_type=excluded.reason_type,
                        reason_text=excluded.reason_text, updated_at=CURRENT_TIMESTAMP
                """
            elif self.db_type == 'postgres':
                query = f"""
                    INSERT INTO suggestion_feedback
                        (user_id, media_user_id, tmdb_id, media_type, feedback, reason_type, reason_text)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                    ON CONFLICT(user_id, media_user_id, tmdb_id, media_type) DO UPDATE SET
                        feedback=EXCLUDED.feedback, reason_type=EXCLUDED.reason_type,
                        reason_text=EXCLUDED.reason_text, updated_at=CURRENT_TIMESTAMP
                """
            else:
                query = f"""
                    INSERT INTO suggestion_feedback
                        (user_id, media_user_id, tmdb_id, media_type, feedback, reason_type, reason_text)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                    ON DUPLICATE KEY UPDATE feedback=VALUES(feedback), reason_type=VALUES(reason_type),
                        reason_text=VALUES(reason_text), updated_at=CURRENT_TIMESTAMP
                """
            cursor.execute(query, (user_id, media_user_id, tmdb_id, media_type, feedback, reason_type, reason_text))
            conn.commit()
        return {
            'feedback': feedback,
            'reason_type': reason_type,
            'reason_text': reason_text,
            'media_user_id': media_user_id,
        }

    def clear_suggestion_feedback(self, suggestion_id, owner_id, user_id, media_user_ids=None):
        """Remove only the caller's feedback for a visible suggestion."""
        ph = self._feedback_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            suggestion = self._feedback_suggestion(cursor, suggestion_id, owner_id, media_user_ids)
            if not suggestion:
                return False
            tmdb_id, media_type, media_user_id = suggestion
            cursor.execute(
                f"DELETE FROM suggestion_feedback WHERE user_id={ph} AND media_user_id={ph} "
                f"AND tmdb_id={ph} AND media_type={ph}",
                (user_id, media_user_id, tmdb_id, media_type),
            )
            removed = cursor.rowcount > 0
            conn.commit()
        return removed

    def get_suggestion_feedback(self, cursor, user_id, tmdb_id, media_type, media_user_id):
        """Return feedback for one internal user/profile/media tuple, if present."""
        ph = self._feedback_placeholder()
        cursor.execute(
            f"SELECT feedback, reason_type, reason_text FROM suggestion_feedback "
            f"WHERE user_id={ph} AND media_user_id={ph} AND tmdb_id={ph} AND media_type={ph}",
            (user_id, self._feedback_media_user_id(media_user_id), str(tmdb_id), media_type),
        )
        row = cursor.fetchone()
        return {'feedback': row[0], 'reason_type': row[1], 'reason_text': row[2]} if row else None

    def should_skip_feedback(self, job_owner_id, tmdb_id, media_type, media_user_id):
        """Whether personal negative feedback should suppress a future automated queue item."""
        if job_owner_id is None:
            return False
        ph = self._feedback_placeholder()
        marks = ','.join([ph] * len(self.NEGATIVE_FEEDBACK))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT 1 FROM suggestion_feedback WHERE user_id={ph} AND media_user_id={ph} "
                f"AND tmdb_id={ph} AND media_type={ph} AND feedback IN ({marks})",
                (job_owner_id, self._feedback_media_user_id(media_user_id), str(tmdb_id), media_type,
                 *sorted(self.NEGATIVE_FEEDBACK)),
            )
            return cursor.fetchone() is not None
