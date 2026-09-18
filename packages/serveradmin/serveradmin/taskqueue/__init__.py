"""Serveradmin - Task queue

Copyright (c) 2026 InnoGames GmbH

A Postgres-backed queue for work that has to happen after a commit but must
not run inside the commit request, for example pushing DNS records to
PowerDNS.  Apps register a ``TaskType`` (see ``registry.py``) that produces
tasks from a commit and runs them later in the ``run_taskqueue`` worker.
"""
