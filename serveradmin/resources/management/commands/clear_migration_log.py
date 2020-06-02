"""Serveradmin - igvm_migration_log cleanup

We are using igvm_migration_log for calculating the overall CPU usage of a
Hypervisor. This is obsolete after the next prime time because the cpu_util_pct
will be correct again. This task will get executed once in the morning to
clean up the log entries from the previous day.

Copyright (c) 2020 InnoGames GmbH
"""
from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand

from adminapi.dataset import Query
from adminapi.filters import Not, Empty


class Command(BaseCommand):
    help = 'Deletes igvm_migration_log entries from previous day'

    def handle(self, *args, **options):
        """Entry point for command

        get all hypervisors which have an entry in igvm_migration_log
        and delete all entries which are from the previous day.
        """

        all_hypervisors = Query({'igvm_migration_log': Not(Empty()),
                                 'servertype': 'hypervisor'},
                           ['igvm_migration_log', 'hostname'])

        now = datetime.now(tz=timezone.utc)

        for hypervisor in all_hypervisors:

            for entry in hypervisor['igvm_migration_log']:
                timestamp = entry.split()[0]

                dt_object_sa = datetime.fromtimestamp(
                    int(timestamp),
                    tz=timezone.utc)

                if dt_object_sa.date() == now.date():
                    continue

                hypervisor['igvm_migration_log'].discard(entry)
                hypervisor.commit()
                self.stdout.write(self.style.SUCCESS(
                    'Delete old entries from {} '.format(
                        hypervisor['hostname'])))
