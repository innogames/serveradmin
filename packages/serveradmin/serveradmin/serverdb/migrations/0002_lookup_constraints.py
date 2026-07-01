# -*- coding: utf-8 -*-

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('serverdb', '0001_initial')]
    operations = [
        migrations.RunSQL(
            'ALTER TABLE servertype '
            'ADD CONSTRAINT servertype_servertype_id_check '
            r"   CHECK (servertype_id ~ '\A[a-z][a-z0-9_]+\Z')"
        ),
        migrations.RunSQL(
            'ALTER TABLE attribute '
            'ADD CONSTRAINT attribute_attribute_id_check '
            r"   CHECK (attribute_id ~ '\A[a-z][a-z0-9_]+\Z'), "
            # Ensure multi is not set on attributes of types that don't
            # support it.
            'ADD CONSTRAINT attribute_multi_check '
            "   CHECK (type NOT IN ('boolean', 'supernet', 'domain') OR"
            '       NOT multi), '
            # Ensure relational attributes are readonly.  As they are virtual
            # and resolved on demand they must be readonly to make sense.
            'ADD CONSTRAINT attribute_readonly_check '
            "   CHECK (type NOT IN ('reverse', 'supernet', 'domain') OR"
            '       readonly), '
            # Ensure relational attributes define their relation target.
            'ADD CONSTRAINT attribute_target_servertype_id_check '
            '   CHECK ('
            "       (type IN ('relation', 'supernet', 'domain')) = "
            '           (target_servertype_id IS NOT NULL)'
            '   ), '
            # Ensure reverse relation attributes are specifying which attribute
            # they are reversing.
            'ADD CONSTRAINT attribute_reversed_attribute_id_check '
            '   CHECK ('
            "       (type = 'reverse') = (reversed_attribute_id IS NOT NULL)"
            '   ), '
            # Ensure attribute value validatation regexps start with \A and end
            # with \Z to make sure they match the whole value.
            'ADD CONSTRAINT attribute_regexp_check '
            r"   CHECK (regexp ~ '\A\\A.*\\Z\Z')"
        ),
    ]
