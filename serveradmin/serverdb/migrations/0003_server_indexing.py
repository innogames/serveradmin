# -*- coding: utf-8 -*-

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('serverdb', '0002_lookup_constraints')]
    operations = [
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS pg_trgm'),
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS btree_gist'),
        migrations.RunSQL(
            'ALTER TABLE server '
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
