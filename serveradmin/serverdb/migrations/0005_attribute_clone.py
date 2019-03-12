from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0004_attribute_value_constraints'),
    ]

    operations = [
        # Mark all previously defined attributes as clonable once.
        migrations.RunSQL(
            'UPDATE attribute '
            'SET clone = true '
            "WHERE type NOT IN ('reverse', 'supernet', 'domain')"
        ),
        # Forbid attributes of relational types from beeing clonable as they
        # can't be written to due to beeing drived from other attributes.
        migrations.RunSQL(
            'ALTER TABLE attribute '
            'ADD CONSTRAINT attribute_clone_check '
            "   CHECK (NOT clone OR type NOT IN ("
            "   'reverse', 'supernet', 'domain'))"
        ),
    ]
