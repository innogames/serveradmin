"""Convert Attribute.target_servertype from ForeignKey to ManyToManyField.

Uses SeparateDatabaseAndState so that:
- Django's state tracker sees standard RemoveField + AddField operations
- The actual DB operations are controlled manually to allow a data
  migration between creating the M2M table and dropping the FK column

Steps:
1. Create the M2M join table
2. Copy existing FK data into the join table
3. Drop the old FK column
"""

import django.db.models
from django.db import migrations, models


def copy_fk_to_m2m(apps, schema_editor):
    """Copy existing target_servertype_id FK values to the new M2M table."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO attribute_target_servertype (attribute_id, servertype_id) "
            "SELECT attribute_id, target_servertype_id FROM attribute "
            "WHERE target_servertype_id IS NOT NULL"
        )


def copy_m2m_to_fk(apps, schema_editor):
    """Reverse: copy M2M values back into the FK column (takes first value)."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "UPDATE attribute SET target_servertype_id = m2m.servertype_id "
            "FROM attribute_target_servertype AS m2m "
            "WHERE attribute.attribute_id = m2m.attribute_id"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0022_attribute_relax_target_servertype_constraints')
    ]

    operations = [
        # Phase 1: Create the M2M join table (DB only, state updated later).
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE TABLE attribute_target_servertype ("
                        "  id BIGSERIAL PRIMARY KEY,"
                        "  attribute_id VARCHAR(32) NOT NULL"
                        "    REFERENCES attribute(attribute_id) ON DELETE CASCADE,"
                        "  servertype_id VARCHAR(32) NOT NULL"
                        "    REFERENCES servertype(servertype_id) ON DELETE CASCADE,"
                        "  UNIQUE (attribute_id, servertype_id)"
                        ")"
                    ),
                    reverse_sql="DROP TABLE IF EXISTS attribute_target_servertype",
                ),
            ],
            state_operations=[],
        ),

        # Phase 2: Copy existing FK data into the M2M table.
        migrations.RunPython(copy_fk_to_m2m, copy_m2m_to_fk),

        # Phase 3: Drop old FK column + constraints; update Django state.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE attribute "
                        "DROP CONSTRAINT IF EXISTS"
                        "  attribute_target_servertype_id_0eab2dcc_fk_servertyp"
                    ),
                    reverse_sql=(
                        "ALTER TABLE attribute ADD CONSTRAINT"
                        "  attribute_target_servertype_id_0eab2dcc_fk_servertyp"
                        "  FOREIGN KEY (target_servertype_id)"
                        "  REFERENCES servertype(servertype_id)"
                        "  DEFERRABLE INITIALLY DEFERRED"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE attribute "
                        "DROP COLUMN IF EXISTS target_servertype_id"
                    ),
                    reverse_sql=(
                        "ALTER TABLE attribute ADD COLUMN target_servertype_id "
                        "VARCHAR(32)"
                    ),
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name='attribute',
                    name='target_servertype',
                ),
                migrations.AddField(
                    model_name='attribute',
                    name='target_servertype',
                    field=models.ManyToManyField(
                        blank=True,
                        help_text='Selecting no servertype allows all servertypes.',
                        to='serverdb.servertype',
                    ),
                ),
            ],
        ),
    ]
