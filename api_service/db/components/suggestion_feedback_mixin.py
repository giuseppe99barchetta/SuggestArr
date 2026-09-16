"""Per-user feedback for queued suggestions.

Feedback intentionally remains separate from the global suggestion blacklist: it is
scoped to the authenticated SuggestArr user and the linked media profile.
"""

import json

from api_service.db.components.suggestion_ownership import ownership_clause


class SuggestionFeedbackMixin:
    NEGATIVE_FEEDBACK = {'not_interested', 'already_seen', 'too_similar'}

    # Feedback that says something about taste. 'already_seen' deliberately is not here:
    # having watched a title is not a verdict on it, so it suppresses the title without
    # claiming the user liked or disliked it.
    TASTE_FEEDBACK = {'interested': 'liked', 'save_for_later': 'liked', 'not_interested': 'disliked'}

    # Titles carried into the recommendation prompt, newest first. The cap is what keeps
    # prompt cost flat as the feedback table grows; suppression stays with the existing
    # post-generation filter, which is not bounded by this number.
    TASTE_PROFILE_LIMIT = 15

    def _feedback_placeholder(self):
        return '%s' if self.db_type in ('mysql', 'mariadb', 'postgres') else '?'

    @staticmethod
    def _feedback_media_user_id(value):
        return '' if value is None else str(value)

    def _feedback_suggestion(self, cursor, suggestion_id, owner_id, media_user_ids=None,
                             include_unassigned=False):
        ph = self._feedback_placeholder()
        query = f"SELECT tmdb_id, media_type, user_id, payload FROM pending_requests WHERE id={ph}"
        params = [suggestion_id]
        owner_clause, owner_params = ownership_clause(self.db_type, owner_id, include_unassigned)
        query += owner_clause
        params.extend(owner_params)
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
                                reason_type=None, reason_text=None, media_user_ids=None,
                                include_unassigned=False, title=None, year=None):
        """Store one user's feedback for a suggestion they are allowed to view."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            suggestion = self._feedback_suggestion(cursor, suggestion_id, owner_id, media_user_ids,
                                                   include_unassigned)
            if not suggestion:
                return None
            tmdb_id, media_type, media_user_id = suggestion
        return self.set_media_feedback(
            user_id, media_user_id, tmdb_id, media_type, feedback, reason_type, reason_text,
            title, year,
        )

    def set_media_feedback(self, user_id, media_user_id, tmdb_id, media_type, feedback,
                           reason_type=None, reason_text=None, title=None, year=None):
        """Store feedback after the caller has verified access to the media item.

        The title and year are denormalised on purpose: the recommendation prompt needs
        names, and resolving hundreds of TMDb ids back to titles on every scheduled run
        would be both slow and an avoidable third-party call.
        """
        ph = self._feedback_placeholder()
        media_user_id = self._feedback_media_user_id(media_user_id)
        title = title.strip()[:500] if isinstance(title, str) and title.strip() else None
        try:
            year = int(year) if year is not None else None
        except (TypeError, ValueError):
            year = None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if self.db_type == 'sqlite':
                query = f"""
                    INSERT INTO suggestion_feedback
                        (user_id, media_user_id, tmdb_id, media_type, feedback, reason_type, reason_text, title, year)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                    ON CONFLICT(user_id, media_user_id, tmdb_id, media_type) DO UPDATE SET
                        feedback=excluded.feedback, reason_type=excluded.reason_type,
                        reason_text=excluded.reason_text,
                        title=COALESCE(excluded.title, suggestion_feedback.title),
                        year=COALESCE(excluded.year, suggestion_feedback.year),
                        updated_at=CURRENT_TIMESTAMP
                """
            elif self.db_type == 'postgres':
                query = f"""
                    INSERT INTO suggestion_feedback
                        (user_id, media_user_id, tmdb_id, media_type, feedback, reason_type, reason_text, title, year)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                    ON CONFLICT(user_id, media_user_id, tmdb_id, media_type) DO UPDATE SET
                        feedback=EXCLUDED.feedback, reason_type=EXCLUDED.reason_type,
                        reason_text=EXCLUDED.reason_text,
                        title=COALESCE(EXCLUDED.title, suggestion_feedback.title),
                        year=COALESCE(EXCLUDED.year, suggestion_feedback.year),
                        updated_at=CURRENT_TIMESTAMP
                """
            else:
                query = f"""
                    INSERT INTO suggestion_feedback
                        (user_id, media_user_id, tmdb_id, media_type, feedback, reason_type, reason_text, title, year)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                    ON DUPLICATE KEY UPDATE feedback=VALUES(feedback), reason_type=VALUES(reason_type),
                        reason_text=VALUES(reason_text),
                        title=COALESCE(VALUES(title), title), year=COALESCE(VALUES(year), year),
                        updated_at=CURRENT_TIMESTAMP
                """
            cursor.execute(query, (user_id, media_user_id, tmdb_id, media_type, feedback, reason_type,
                                   reason_text, title, year))
            conn.commit()
        return {
            'feedback': feedback,
            'reason_type': reason_type,
            'reason_text': reason_text,
            'media_user_id': media_user_id,
        }

    def clear_suggestion_feedback(self, suggestion_id, owner_id, user_id, media_user_ids=None,
                                  include_unassigned=False):
        """Remove only the caller's feedback for a visible suggestion."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            suggestion = self._feedback_suggestion(cursor, suggestion_id, owner_id, media_user_ids,
                                                   include_unassigned)
            if not suggestion:
                return False
            tmdb_id, media_type, media_user_id = suggestion
        return self.clear_media_feedback(user_id, media_user_id, tmdb_id, media_type)

    def clear_media_feedback(self, user_id, media_user_id, tmdb_id, media_type):
        """Delete feedback after the caller has verified access to the media item."""
        ph = self._feedback_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM suggestion_feedback WHERE user_id={ph} AND media_user_id={ph} "
                f"AND tmdb_id={ph} AND media_type={ph}",
                (user_id, self._feedback_media_user_id(media_user_id), str(tmdb_id), media_type),
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

    def get_suggestion_feedback_signals(self, user_id, media_user_id, media_type):
        """Return feedback values used for local ranking for one user/profile."""
        ph = self._feedback_placeholder()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT tmdb_id, feedback FROM suggestion_feedback "
                f"WHERE user_id={ph} AND media_user_id={ph} AND media_type={ph}",
                (user_id, self._feedback_media_user_id(media_user_id), media_type),
            )
            return {str(row[0]): row[1] for row in cursor.fetchall()}

    def get_taste_profile(self, user_id, media_user_id, media_type, limit=None):
        """Return the recent liked/disliked titles that shape the recommendation prompt.

        Only rows that carry a title are usable, so feedback saved before the title
        column existed is skipped rather than sent to the model as a bare id.

        :return: Dict with 'liked' and 'disliked' lists of {'title', 'year'}, newest first.
        """
        if user_id is None:
            return {'liked': [], 'disliked': []}
        limit = self.TASTE_PROFILE_LIMIT if limit is None else limit
        if limit <= 0:
            return {'liked': [], 'disliked': []}
        ph = self._feedback_placeholder()
        marks = ','.join([ph] * len(self.TASTE_FEEDBACK))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT title, year, feedback FROM suggestion_feedback "
                f"WHERE user_id={ph} AND media_user_id={ph} AND media_type={ph} "
                f"AND feedback IN ({marks}) AND title IS NOT NULL "
                f"ORDER BY updated_at DESC LIMIT {ph}",
                (user_id, self._feedback_media_user_id(media_user_id), media_type,
                 *sorted(self.TASTE_FEEDBACK), limit),
            )
            profile = {'liked': [], 'disliked': []}
            for title, year, feedback in cursor.fetchall():
                bucket = self.TASTE_FEEDBACK.get(feedback)
                if bucket:
                    profile[bucket].append({'title': title, 'year': year})
            return profile

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
