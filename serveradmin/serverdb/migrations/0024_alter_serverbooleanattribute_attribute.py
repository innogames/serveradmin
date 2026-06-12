import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0023_attribute_multi_target_servertype'),
    ]

    operations = [
        # Drop obsolete indexes. The like one is not required because we do not
        # support (fuzzy) search for attribute ids and the other one is
        # redundant.
        migrations.RunSQL(
            sql=[
                "DROP INDEX IF EXISTS "
                "server_boolean_attribute_attribute_id_b1ad575f;",
                "DROP INDEX IF EXISTS "
                "server_boolean_attribute_attribute_id_b1ad575f_like;",
            ],
            reverse_sql=[
                "CREATE INDEX server_boolean_attribute_attribute_id_b1ad575f "
                "ON server_boolean_attribute (attribute_id);",
                "CREATE INDEX "
                "server_boolean_attribute_attribute_id_b1ad575f_like "
                "ON server_boolean_attribute (attribute_id varchar_pattern_ops);",
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='serverbooleanattribute',
                    name='attribute',
                    field=models.ForeignKey(
                        db_index=False,
                        limit_choices_to={'type': 'boolean'},
                        on_delete=django.db.models.deletion.CASCADE,
                        to='serverdb.attribute',
                    ),
                ),
            ],
        ),
    ]
