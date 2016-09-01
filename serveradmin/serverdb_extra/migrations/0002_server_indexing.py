# -*- coding: utf-8 -*-

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('serverdb_extra', '0001_lookup_constraints')]
    operations = [
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS pg_trgm'),
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS btree_gist'),
        migrations.RunSQL(
            'ALTER TABLE server '
            'ADD CONSTRAINT server_hostname_check '
            "   CHECK (hostname ~ '^[a-z][a-z0-9\\.\\-]*$'),"
            'ADD CONSTRAINT server_inter_ip_exclude '
            '   EXCLUDE USING gist ('
            '       intern_ip inet_ops WITH &&,'
            '       servertype_id WITH ='
            '   )'
            "   WHERE (servertype_id != 'loadbalancer')"
        ),
        migrations.RunSQL(
            'CREATE INDEX server_hostname_trgm '
            'ON server USING gin (hostname gin_trgm_ops)'
        ),
    ]
