from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0004_attribute_value_constraints'),
    ]

    operations = [
        migrations.RunSQL(
            'UPDATE attribute '
            'SET clone = true '
            "WHERE type NOT IN ('reverse', 'supernet', 'domain')"
        ),
        migrations.RunSQL(
            'ALTER TABLE attribute '
            'ADD CONSTRAINT attribute_clone_check '
            "   CHECK (NOT clone OR type NOT IN ("
            "   'reverse', 'supernet', 'domain'))"
        ),
    ]
