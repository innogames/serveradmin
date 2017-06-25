# -*- coding: utf-8 -*-

from django.db import migrations


class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL(
            'ALTER TABLE project '
            'ADD CONSTRAINT project_project_id_check '
            r"   CHECK (project_id ~ '\A[a-z][a-z0-9_]*\Z'), "
            'ADD CONSTRAINT project_subdomain_check '
            r"   CHECK (subdomain ~ '\A[a-z][a-z0-9\.\-]*\Z')"
        ),
        migrations.RunSQL(
            'ALTER TABLE servertype '
            'ADD CONSTRAINT servertype_servertype_id_check '
            r"   CHECK (servertype_id ~ '\A[a-z][a-z0-9_]*\Z')"
        ),
        migrations.RunSQL(
            'ALTER TABLE attribute '
            'ADD CONSTRAINT attribute_attribute_id_check '
            r"   CHECK (attribute_id ~ '\A[a-z][a-z0-9_]*\Z'), "
            'ADD CONSTRAINT attribute_multi_check '
            '   CHECK ('
            "       type NOT IN ('boolean', 'supernet') OR NOT multi"
            '   ), '
            'ADD CONSTRAINT attribute_readonly_check '
            '   CHECK ('
            "       type NOT IN ('reverse_hostname', 'supernet') OR readonly"
            '   ), '
            'ADD CONSTRAINT attribute_target_servertype_id_check '
            '   CHECK ('
            "       (type IN ('hostname', 'supernet')) = "
            '           (target_servertype_id IS NOT NULL)'
            '   ), '
            'ADD CONSTRAINT attribute_reversed_attribute_id_check '
            '   CHECK ('
            "       (type = 'reverse_hostname') = "
            '           (reversed_attribute_id IS NOT NULL)'
            '   )'
        ),
    ]
