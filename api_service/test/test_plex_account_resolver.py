"""Tests for reconciling plex.tv account ids with a Plex server's own ids.

Plex reports the server owner as a local account (typically id 1) while
plex.tv OAuth returns their global account id. A profile stored under the
plex.tv id matches no monitored user, so watch-tracker links attached to it
silently contribute nothing.

Strategy: the matching rules are covered as pure functions; the repair path
runs against a real temp SQLite database so the claim that Simkl and Trakt
links survive the rename is actually exercised rather than mocked.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

import logging
logging.disable(logging.CRITICAL)

from api_service.services.plex.account_resolver import (
    canonical_plex_account_id,
    reconcile_plex_profiles,
)


# The shape of a real server list: the owner is a local account with a small
# id, everyone else carries their plex.tv id.
SERVER_USERS = [
    {"id": 1, "name": "Wirewraith"},
    {"id": 3502706, "name": "somepotato"},
    {"id": 18397891, "name": "cassielouwho"},
]


class TestCanonicalPlexAccountId(unittest.TestCase):

    def test_owner_plex_tv_id_maps_to_their_local_account(self):
        self.assertEqual(
            canonical_plex_account_id(SERVER_USERS, "14621895", "Wirewraith"), "1",
        )

    def test_shared_user_id_is_already_correct(self):
        self.assertEqual(
            canonical_plex_account_id(SERVER_USERS, "3502706", "somepotato"), "3502706",
        )

    def test_id_present_on_the_server_wins_over_any_name(self):
        # An id the server knows is authoritative; a mismatched display name
        # must not drag the account somewhere else.
        self.assertEqual(
            canonical_plex_account_id(SERVER_USERS, "3502706", "Wirewraith"), "3502706",
        )

    def test_name_match_ignores_case_and_padding(self):
        self.assertEqual(
            canonical_plex_account_id(SERVER_USERS, "14621895", "  wirewraith "), "1",
        )

    def test_unknown_account_is_left_alone(self):
        self.assertEqual(
            canonical_plex_account_id(SERVER_USERS, "999", "a-stranger"), "999",
        )

    def test_missing_username_cannot_be_matched(self):
        self.assertEqual(canonical_plex_account_id(SERVER_USERS, "999", None), "999")
        self.assertEqual(canonical_plex_account_id(SERVER_USERS, "999", ""), "999")

    def test_unreachable_server_changes_nothing(self):
        self.assertEqual(canonical_plex_account_id([], "14621895", "Wirewraith"), "14621895")

    def test_duplicate_names_are_too_ambiguous_to_match(self):
        # Guessing here could attach one person's watch history to another.
        users = [{"id": 1, "name": "Sam"}, {"id": 2, "name": "sam"}]
        self.assertEqual(canonical_plex_account_id(users, "999", "Sam"), "999")

    def test_server_entries_without_a_name_are_skipped(self):
        users = [{"id": 1, "name": None}, {"id": 2, "name": "Wirewraith"}]
        self.assertEqual(canonical_plex_account_id(users, "999", "Wirewraith"), "2")


class _DBBase(unittest.TestCase):
    """Fresh temp-file SQLite database per test, as elsewhere in the suite."""

    def setUp(self):
        import api_service.db.database_manager as dm_mod

        dm_mod.DatabaseManager._instance = None
        fd, self._db_file = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self._path_patch = patch.object(dm_mod, 'DB_PATH', self._db_file)
        self._path_patch.start()
        self._env_patch = patch(
            'api_service.db.database_manager.load_env_vars',
            return_value={'DB_TYPE': 'sqlite'},
        )
        self._env_patch.start()

        from api_service.db.database_manager import DatabaseManager
        self.db = DatabaseManager()

    def tearDown(self):
        import api_service.db.database_manager as dm_mod
        dm_mod.DatabaseManager._instance = None
        self._path_patch.stop()
        self._env_patch.stop()
        try:
            os.unlink(self._db_file)
        except FileNotFoundError:
            pass

    def _user(self, username='wire'):
        return self.db.create_auth_user(username, 'dummy_hash', role='admin')

    def _link_simkl(self, identity_id, username='wire_simkl'):
        return self.db.upsert_simkl_account_link(
            media_user_identity_id=identity_id,
            simkl_user_id='s1',
            simkl_username=username,
            status='connected',
        )


class TestMoveMediaUserIdentity(_DBBase):

    def test_move_keeps_the_row_and_its_links(self):
        identity = self.db.upsert_media_user_identity('plex', '14621895', 'Wirewraith')
        self._link_simkl(identity['id'])

        self.assertTrue(self.db.move_media_user_identity('plex', '14621895', '1'))

        moved = self.db.get_media_user_identity('plex', '1')
        self.assertEqual(moved['id'], identity['id'])
        self.assertEqual(moved['external_username'], 'Wirewraith')
        self.assertTrue(self.db.get_simkl_account_link(identity['id'])['connected'])
        with self.assertRaises(ValueError):
            self.db.get_media_user_identity('plex', '14621895')

    def test_a_target_with_linked_data_is_not_clobbered(self):
        # Merging would have to discard one of two sets of tracker links, so
        # the move declines instead.
        old = self.db.upsert_media_user_identity('plex', '14621895', 'Wirewraith')
        target = self.db.upsert_media_user_identity('plex', '1', 'Someone Else')
        self._link_simkl(target['id'])
        uid = self._user()
        self.db.create_user_media_profile(uid, 'plex', '14621895', 'Wirewraith')

        self.assertFalse(self.db.move_media_user_identity('plex', '14621895', '1', user_id=uid))

        self.assertEqual(self.db.get_media_user_identity('plex', '1')['id'], target['id'])
        self.assertEqual(self.db.get_media_user_identity('plex', '14621895')['id'], old['id'])
        self.assertEqual(self.db.get_user_media_profiles(uid)[0]['external_user_id'], '14621895')

    def test_an_empty_target_is_absorbed(self):
        old = self.db.upsert_media_user_identity('plex', '14621895', 'Wirewraith')
        self.db.upsert_media_user_identity('plex', '1', 'Wirewraith')

        self.assertTrue(self.db.move_media_user_identity('plex', '14621895', '1'))
        self.assertEqual(self.db.get_media_user_identity('plex', '1')['id'], old['id'])

    def test_the_profile_moves_with_the_identity_and_keeps_its_token(self):
        # The full profile upsert rewrites every column, so using it here
        # would blank the Plex token and break server-side calls.
        uid = self._user()
        self.db.create_user_media_profile(uid, 'plex', '14621895', 'Wirewraith', access_token='tok')
        self.db.upsert_media_user_identity('plex', '14621895', 'Wirewraith')

        self.assertTrue(self.db.move_media_user_identity('plex', '14621895', '1', user_id=uid))

        self.assertEqual(self.db.get_user_media_profile_token(uid, 'plex'), 'tok')
        self.assertEqual(self.db.get_user_media_profiles(uid)[0]['external_user_id'], '1')

    def test_moving_a_missing_identity_still_repoints_the_profile(self):
        uid = self._user()
        self.db.create_user_media_profile(uid, 'plex', '14621895', 'Wirewraith')

        self.assertTrue(self.db.move_media_user_identity('plex', '14621895', '1', user_id=uid))
        self.assertEqual(self.db.get_user_media_profiles(uid)[0]['external_user_id'], '1')

    def test_other_providers_are_untouched(self):
        jelly = self.db.upsert_media_user_identity('jellyfin', '14621895', 'Wirewraith')
        self.db.upsert_media_user_identity('plex', '14621895', 'Wirewraith')
        self.db.move_media_user_identity('plex', '14621895', '1')
        self.assertEqual(
            self.db.get_media_user_identity('jellyfin', '14621895')['id'], jelly['id'],
        )

    def test_profiles_are_listed_per_provider_without_tokens(self):
        uid = self._user()
        self.db.create_user_media_profile(uid, 'plex', '14621895', 'Wirewraith', access_token='tok')
        self.db.create_user_media_profile(uid, 'jellyfin', 'jf-1', 'Wire')

        rows = self.db.get_media_profiles_by_provider('plex')

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['external_user_id'], '14621895')
        self.assertNotIn('access_token', rows[0])


class TestReconcilePlexProfiles(_DBBase):

    def _stranded_profile(self):
        uid = self._user()
        self.db.create_user_media_profile(
            uid, 'plex', '14621895', 'Wirewraith', access_token='tok',
        )
        identity = self.db.upsert_media_user_identity('plex', '14621895', 'Wirewraith')
        self._link_simkl(identity['id'])
        return uid, identity

    def test_a_stranded_profile_is_repaired(self):
        uid, _ = self._stranded_profile()

        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 1)

        self.assertEqual(
            self.db.get_user_media_profiles(uid)[0]['external_user_id'], '1',
        )

    def test_the_simkl_link_follows_the_repair(self):
        # The point of the repair: the job looks up plex/1, and the link that
        # used to hang off the plex.tv id must be found there.
        self._stranded_profile()
        reconcile_plex_profiles(self.db, lambda: SERVER_USERS)

        identity = self.db.get_media_user_identity('plex', '1')
        self.assertTrue(self.db.get_simkl_account_link(identity['id'])['connected'])

    def test_repair_keeps_the_access_token(self):
        uid, _ = self._stranded_profile()
        reconcile_plex_profiles(self.db, lambda: SERVER_USERS)
        self.assertEqual(self.db.get_user_media_profile_token(uid, 'plex'), 'tok')

    def test_an_empty_unclaimed_target_is_absorbed_before_repair(self):
        uid, old_identity = self._stranded_profile()
        self.db.upsert_media_user_identity('plex', '1', 'Wirewraith')

        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 1)
        self.assertEqual(
            self.db.get_user_media_profiles(uid)[0]['external_user_id'], '1',
        )
        self.assertEqual(
            self.db.get_media_user_identity('plex', '1')['id'], old_identity['id'],
        )
        self.assertTrue(self.db.get_simkl_account_link(old_identity['id'])['connected'])

    def test_an_already_correct_profile_is_left_alone(self):
        uid = self._user()
        self.db.create_user_media_profile(uid, 'plex', '3502706', 'somepotato')

        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 0)

        self.assertEqual(
            self.db.get_user_media_profiles(uid)[0]['external_user_id'], '3502706',
        )

    def test_an_unreachable_server_changes_nothing(self):
        uid, _ = self._stranded_profile()

        self.assertEqual(reconcile_plex_profiles(self.db, lambda: []), 0)

        self.assertEqual(
            self.db.get_user_media_profiles(uid)[0]['external_user_id'], '14621895',
        )

    def test_the_server_is_not_queried_when_no_plex_profiles_exist(self):
        # Keeps boot free of a pointless network call on Jellyfin or Emby
        # installs.
        uid = self._user()
        self.db.create_user_media_profile(uid, 'jellyfin', 'jf-1', 'Wire')

        calls = []

        def lister():
            calls.append(1)
            return SERVER_USERS

        self.assertEqual(reconcile_plex_profiles(self.db, lister), 0)
        self.assertEqual(calls, [])

    def test_the_server_is_queried_once_for_many_profiles(self):
        for index in range(3):
            uid = self._user(f'user{index}')
            self.db.create_user_media_profile(uid, 'plex', f'unknown-{index}', f'user{index}')

        calls = []

        def lister():
            calls.append(1)
            return SERVER_USERS

        reconcile_plex_profiles(self.db, lister)
        self.assertEqual(len(calls), 1)

    def test_repair_is_idempotent(self):
        self._stranded_profile()
        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 1)
        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 0)

    def test_a_failed_profile_update_rolls_back_the_identity_move(self):
        """A failure mid-migration must not leave identity and profile apart."""
        import sqlite3
        uid, identity = self._stranded_profile()
        self._fail_profile_updates()

        with self.assertRaises(sqlite3.DatabaseError):
            reconcile_plex_profiles(self.db, lambda: SERVER_USERS)

        self.assertEqual(self.db.get_user_media_profiles(uid)[0]['external_user_id'], '14621895')
        self.assertEqual(self.db.get_media_user_identity('plex', '14621895')['id'], identity['id'])

        # Once the failure clears, the next run completes the repair.
        self._allow_profile_updates()
        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 1)
        self.assertEqual(self.db.get_user_media_profiles(uid)[0]['external_user_id'], '1')
        self.assertTrue(
            self.db.get_simkl_account_link(
                self.db.get_media_user_identity('plex', '1')['id'])['connected'],
        )

    def test_a_half_moved_profile_is_recovered(self):
        """Identity already on the server id, profile still on the plex.tv id."""
        uid, identity = self._stranded_profile()
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE media_user_identities SET external_user_id = '1' WHERE id = ?",
                (identity['id'],),
            )
            conn.commit()

        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 1)
        self.assertEqual(self.db.get_user_media_profiles(uid)[0]['external_user_id'], '1')

    def _fail_profile_updates(self):
        with self.db.get_connection() as conn:
            conn.execute(
                "CREATE TRIGGER fail_profile_update BEFORE UPDATE ON user_media_profiles "
                "BEGIN SELECT RAISE(ABORT, 'forced profile update failure'); END"
            )
            conn.commit()

    def _allow_profile_updates(self):
        with self.db.get_connection() as conn:
            conn.execute("DROP TRIGGER fail_profile_update")
            conn.commit()


class TestReconcileCollisions(_DBBase):
    """Two profiles must never be re-pointed at one Plex user.

    user_media_profiles is unique only on (user_id, provider), so nothing in
    the schema prevents it, and the mapping itself rests on a display-name
    match. Merging two people's requests and watch history is worse than
    leaving an id that resolves to nothing, so a contested target is skipped.
    """

    _seq = 0

    def _profile(self, plex_username, external_id):
        """A SuggestArr account whose Plex profile carries `plex_username`.

        The auth username is incidental and must be unique; the Plex display
        name is the one the reconciler actually matches on, so collisions are
        created there.
        """
        TestReconcileCollisions._seq += 1
        uid = self._user(f'account{TestReconcileCollisions._seq}')
        self.db.create_user_media_profile(uid, 'plex', external_id, plex_username)
        return uid

    def test_a_target_another_profile_already_holds_is_left_alone(self):
        holder = self._profile('Wirewraith', '1')
        contender = self._profile('Wirewraith', '14621895')

        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 0)

        self.assertEqual(
            self.db.get_user_media_profiles(holder)[0]['external_user_id'], '1',
        )
        self.assertEqual(
            self.db.get_user_media_profiles(contender)[0]['external_user_id'], '14621895',
        )

    def test_two_stranded_profiles_cannot_both_claim_one_server_id(self):
        first = self._profile('Wirewraith', '14621895')
        second = self._profile('Wirewraith', '99999999')

        reconcile_plex_profiles(self.db, lambda: SERVER_USERS)

        stored = {
            self.db.get_user_media_profiles(first)[0]['external_user_id'],
            self.db.get_user_media_profiles(second)[0]['external_user_id'],
        }
        self.assertEqual(len(stored), 2)
        self.assertIn('1', stored)

    def test_the_losers_identity_and_tracker_links_are_left_where_they_were(self):
        """Declining the repair must not half-move the loser's identity."""
        self._profile('Wirewraith', '14621895')
        loser = self._profile('Wirewraith', '99999999')
        identity = self.db.upsert_media_user_identity('plex', '99999999', 'Wirewraith')
        self._link_simkl(identity['id'])

        reconcile_plex_profiles(self.db, lambda: SERVER_USERS)

        self.assertEqual(
            self.db.get_user_media_profiles(loser)[0]['external_user_id'], '99999999',
        )
        still_there = self.db.get_media_user_identity('plex', '99999999')
        self.assertEqual(still_there['id'], identity['id'])
        self.assertTrue(self.db.get_simkl_account_link(identity['id'])['connected'])

    def test_an_uncontested_repair_still_happens_alongside_a_contested_one(self):
        blocked = self._profile('Wirewraith', '14621895')
        self._profile('Wirewraith', '1')
        # cassielouwho is stranded under a plex.tv id nobody else wants.
        free = self._profile('cassielouwho', '77777777')

        self.assertEqual(reconcile_plex_profiles(self.db, lambda: SERVER_USERS), 1)

        self.assertEqual(
            self.db.get_user_media_profiles(free)[0]['external_user_id'], '18397891',
        )
        self.assertEqual(
            self.db.get_user_media_profiles(blocked)[0]['external_user_id'], '14621895',
        )


if __name__ == '__main__':
    unittest.main()
