"""Serveradmin

Remove no-op entries from the changelog

Copyright (c) 2026 InnoGames GmbH
"""

from time import monotonic, sleep

from django.core.management import BaseCommand, CommandError
from django.db import connection, transaction

# A no-op entry is an attribute change that did not change the stored value.
# The "strict" stage compares old and new as jsonb, which is exact but treats
# the string "8192" and the number 8192 as different.  The "loose" stage
# compares their text representation to catch exactly those leftovers.
PREDICATES = {
    'strict': """
        (e.value ->> 'action' = 'update'
         AND e.value -> 'old' = e.value -> 'new')
        OR (e.value ->> 'action' = 'multi'
            AND COALESCE(e.value -> 'add', '[]'::jsonb) = '[]'::jsonb
            AND COALESCE(e.value -> 'remove', '[]'::jsonb) = '[]'::jsonb)
    """,
    'loose': """
        e.value ->> 'action' = 'update'
        AND e.value ->> 'old' = e.value ->> 'new'
    """,
}

# Per change row in the id range: how many attribute entries it has, how many
# of them are no-ops and which ones.  Only rows with at least one no-op end
# up in the temporary table.
ANALYSE_SQL = """
    CREATE TEMP TABLE noop_by_change ON COMMIT DROP AS
    SELECT change_id,
           commit_id,
           count(*) AS key_count,
           count(*) FILTER (WHERE is_noop) AS noop_count,
           array_agg(attribute_id) FILTER (WHERE is_noop) AS noop_attrs
    FROM (
        SELECT c.id        AS change_id,
               c.commit_id AS commit_id,
               e.key       AS attribute_id,
               ({predicate}) AS is_noop
        FROM serverdb_change AS c
        CROSS JOIN LATERAL jsonb_each(c.change_json) AS e(key, value)
        WHERE c.id >= %s
          AND c.id < %s
          AND c.change_type = 'change'
          AND e.key <> 'object_id'
    ) AS entries
    GROUP BY change_id, commit_id
    HAVING bool_or(is_noop)
"""

# Rows that mix real and no-op entries only lose the no-op keys.
STRIP_SQL = """
    UPDATE serverdb_change AS c
    SET change_json = c.change_json - n.noop_attrs
    FROM noop_by_change AS n
    WHERE n.change_id = c.id
      AND n.noop_count < n.key_count
"""

# Rows consisting of no-ops only are removed.
DELETE_ROWS_SQL = """
    DELETE FROM serverdb_change AS c
    USING noop_by_change AS n
    WHERE n.change_id = c.id
      AND n.noop_count = n.key_count
"""

# Commits that lost their last row above are removed as well.
DELETE_COMMITS_SQL = """
    DELETE FROM serverdb_changecommit AS cc
    USING (
        SELECT DISTINCT commit_id
        FROM noop_by_change
        WHERE noop_count = key_count
    ) AS d
    WHERE cc.id = d.commit_id
      AND NOT EXISTS (
          SELECT 1 FROM serverdb_change AS c WHERE c.commit_id = cc.id
      )
"""

DROP_SQL = 'DROP TABLE IF EXISTS noop_by_change'


class Command(BaseCommand):
    help = (
        'Remove no-op entries from the changelog, e.g. memory: 8192 => 8192. '
        'Rows consisting only of no-ops are deleted together with commits '
        'that have no row left, rows mixing real and no-op entries lose the '
        'no-op keys. Works in id ranges of serverdb_change, one transaction '
        'per batch, and is safe to rerun or resume with --start-id. '
        'Suggested procedure: --dry-run on a range first, then --stage '
        'strict, then --stage loose, and VACUUM ANALYZE both tables after.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--stage', choices=['strict', 'loose', 'all'], default='all',
            help='strict: jsonb equality and empty multi changes; loose: '
                 'text equality, catches string vs. number leftovers; all: '
                 'strict followed by loose (default)',
        )
        parser.add_argument(
            '--batch-size', type=int, default=100000,
            help='Width of the serverdb_change.id range per transaction '
                 '(default: 100000)',
        )
        parser.add_argument(
            '--start-id', type=int,
            help='First serverdb_change.id to process (default: lowest id)',
        )
        parser.add_argument(
            '--end-id', type=int,
            help='Last serverdb_change.id to process, inclusive '
                 '(default: highest id)',
        )
        parser.add_argument(
            '--sleep', type=float, default=0.0,
            help='Seconds to pause between batches (default: 0)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Roll back every batch, only report what would happen',
        )

    def handle(self, *args, **options):
        if options['batch_size'] < 1:
            raise CommandError('--batch-size must be at least 1')

        stages = ['strict', 'loose']
        if options['stage'] != 'all':
            stages = [options['stage']]

        with connection.cursor() as cursor:
            cursor.execute('SELECT min(id), max(id) FROM serverdb_change')
            min_id, max_id = cursor.fetchone()

        if min_id is None:
            self.stdout.write('No change rows found, nothing to do.')
            return

        start = options['start_id'] or min_id
        end = (options['end_id'] or max_id) + 1    # exclusive
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                'Dry run: every batch is rolled back.'))

        grand_total = [0, 0, 0]
        for stage in stages:
            totals = self._run_stage(stage, start, end, options)
            for i, count in enumerate(totals):
                grand_total[i] += count

        if len(stages) > 1:
            self.stdout.write(self.style.SUCCESS(
                f'Total: stripped {grand_total[0]}, deleted '
                f'{grand_total[1]} rows and {grand_total[2]} commits'))

    def _run_stage(self, stage, start, end, options):
        """Walk the id range in batches for one stage, return the totals"""
        self.stdout.write(
            f'Stage {stage}: ids {start} to {end - 1}, '
            f'batch size {options["batch_size"]}')
        totals = [0, 0, 0]
        lo = start
        while lo < end:
            hi = min(lo + options['batch_size'], end)
            started = monotonic()
            counts = self._run_batch(stage, lo, hi, options['dry_run'])
            self.stdout.write(
                f'  {lo}-{hi - 1}: stripped {counts[0]}, deleted '
                f'{counts[1]} rows and {counts[2]} commits '
                f'({monotonic() - started:.1f}s)')
            for i, count in enumerate(counts):
                totals[i] += count
            lo = hi
            if options['sleep'] and lo < end:
                sleep(options['sleep'])

        self.stdout.write(self.style.SUCCESS(
            f'Stage {stage} done: stripped {totals[0]}, deleted '
            f'{totals[1]} rows and {totals[2]} commits'))
        return totals

    def _run_batch(self, stage, lo, hi, dry_run):
        """Clean one id range in a single transaction

        Returns (rows stripped, rows deleted, commits deleted).
        """
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL work_mem = '256MB'")
            cursor.execute(DROP_SQL)
            cursor.execute(
                ANALYSE_SQL.format(predicate=PREDICATES[stage]), [lo, hi])
            cursor.execute(STRIP_SQL)
            stripped = cursor.rowcount
            cursor.execute(DELETE_ROWS_SQL)
            deleted_rows = cursor.rowcount
            cursor.execute(DELETE_COMMITS_SQL)
            deleted_commits = cursor.rowcount
            cursor.execute(DROP_SQL)

            if dry_run:
                transaction.set_rollback(True)

        return stripped, deleted_rows, deleted_commits
