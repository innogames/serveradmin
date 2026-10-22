"""Serveradmin - cleanup_noop_changes management command tests

Copyright (c) 2026 InnoGames GmbH
"""

from io import StringIO

from django.core.management import call_command
from django.test import TransactionTestCase

from serveradmin.serverdb.models import Change, ChangeCommit

REAL = {'action': 'update', 'old': 'squeeze', 'new': 'wheezy'}
NOOP = {'action': 'update', 'old': 8192, 'new': 8192}
NOOP_TYPED = {'action': 'update', 'old': '8192', 'new': 8192}
MULTI_EMPTY = {'action': 'multi', 'add': [], 'remove': []}
MULTI_REAL = {'action': 'multi', 'add': ['x'], 'remove': []}


class CleanupNoopChangesTest(TransactionTestCase):

    def _commit(self, *rows, change_type=Change.Type.CHANGE):
        """Create a commit with one Change row per given dict"""
        commit = ChangeCommit.objects.create()
        for object_id, attributes in enumerate(rows, start=1):
            Change.objects.create(
                object_id=object_id,
                change_type=change_type,
                change_json={'object_id': object_id, **attributes},
                commit=commit,
            )
        return commit

    def _run(self, **options):
        out = StringIO()
        call_command('cleanup_noop_changes', stdout=out, **options)
        return out.getvalue()

    def test_noop_row_and_its_commit_are_deleted(self):
        commit = self._commit({'memory': NOOP})

        self._run(stage='strict')

        self.assertFalse(Change.objects.exists())
        self.assertFalse(ChangeCommit.objects.filter(pk=commit.pk).exists())

    def test_empty_multi_is_deleted(self):
        self._commit({'database': MULTI_EMPTY})

        self._run(stage='strict')

        self.assertFalse(Change.objects.exists())
        self.assertFalse(ChangeCommit.objects.exists())

    def test_mixed_row_keeps_real_entries(self):
        commit = self._commit({'os': REAL, 'memory': NOOP, 'db': MULTI_EMPTY})

        self._run(stage='strict')

        change = Change.objects.get()
        self.assertEqual(change.commit, commit)
        self.assertEqual(change.change_json, {'object_id': 1, 'os': REAL})

    def test_commit_with_real_row_survives(self):
        commit = self._commit({'os': REAL}, {'memory': NOOP})

        self._run(stage='strict')

        change = Change.objects.get()
        self.assertEqual(change.object_id, 1)
        self.assertTrue(ChangeCommit.objects.filter(pk=commit.pk).exists())

    def test_real_changes_are_untouched(self):
        self._commit(
            {'os': REAL},
            {'os': {'action': 'new', 'new': 'wheezy'}},
            {'os': {'action': 'delete', 'old': 'wheezy'}},
            {'os': {'action': 'update', 'old': 'wheezy', 'new': None}},
            {'database': MULTI_REAL},
        )
        self._commit({'hostname': 'x', 'memory': 1},
                     change_type=Change.Type.CREATE)
        self._commit({'hostname': 'y', 'memory': 1},
                     change_type=Change.Type.DELETE)
        before = list(Change.objects.order_by('pk').values_list(
            'pk', 'change_type', 'change_json'))

        self._run()

        after = list(Change.objects.order_by('pk').values_list(
            'pk', 'change_type', 'change_json'))
        self.assertEqual(before, after)
        self.assertEqual(ChangeCommit.objects.count(), 3)

    def test_type_mismatch_needs_loose_stage(self):
        self._commit({'memory': NOOP_TYPED})

        self._run(stage='strict')
        self.assertEqual(Change.objects.count(), 1)

        self._run(stage='loose')
        self.assertFalse(Change.objects.exists())
        self.assertFalse(ChangeCommit.objects.exists())

    def test_all_stages_run_strict_then_loose(self):
        self._commit({'memory': NOOP}, {'memory': NOOP_TYPED})

        output = self._run()

        self.assertFalse(Change.objects.exists())
        self.assertFalse(ChangeCommit.objects.exists())
        self.assertIn('Stage strict done', output)
        self.assertIn('Stage loose done', output)

    def test_dry_run_changes_nothing(self):
        self._commit({'memory': NOOP}, {'os': REAL, 'memory': NOOP})

        output = self._run(stage='strict', dry_run=True)

        self.assertIn('stripped 1, deleted 1 rows and 0 commits', output)
        self.assertEqual(Change.objects.count(), 2)
        self.assertEqual(ChangeCommit.objects.count(), 1)

    def test_small_batches_cover_everything(self):
        for _ in range(5):
            self._commit({'memory': NOOP})
        self._commit({'os': REAL})

        output = self._run(stage='strict', batch_size=2)

        self.assertEqual(Change.objects.count(), 1)
        self.assertEqual(ChangeCommit.objects.count(), 1)
        self.assertIn('deleted 5 rows and 5 commits', output)

    def test_id_range_limits_the_run(self):
        first = self._commit({'memory': NOOP})
        second = self._commit({'memory': NOOP})
        last_id = Change.objects.get(commit=second).pk

        self._run(stage='strict', start_id=last_id, end_id=last_id)

        self.assertTrue(Change.objects.filter(commit=first).exists())
        self.assertFalse(Change.objects.filter(commit=second).exists())

    def test_empty_table(self):
        output = self._run()

        self.assertIn('nothing to do', output)
