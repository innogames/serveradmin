# -*- coding: utf-8 -*-

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('serverdb', '0002_lookup_constraints')]
    operations = [
        # Add a pg_trgm based trigram index on the server hostname.
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS pg_trgm'),
        migrations.RunSQL(
            'CREATE INDEX server_hostname_trgm '
            'ON server USING gin (hostname gin_trgm_ops)'
        ),
        # Ensure objects within the same servertype have a unique intern_ip.
        migrations.RunSQL('CREATE EXTENSION IF NOT EXISTS btree_gist'),
        migrations.RunSQL(
            'ALTER TABLE server '
            'ADD CONSTRAINT server_inter_ip_exclude '
            '   EXCLUDE USING gist ('
            '       intern_ip inet_ops WITH &&,'
            '       servertype_id WITH ='
            '   )'
            # At InnoGames we have a servertype loadbalancer which is the only
            # servertype allowed to have multiple objects sharing the same
            # intern_ip.  We use this to forward different ports to different
            # hosts as well as for multi datacenter virtual IPs.
            "   WHERE (servertype_id != 'loadbalancer')"
        ),
    ]
