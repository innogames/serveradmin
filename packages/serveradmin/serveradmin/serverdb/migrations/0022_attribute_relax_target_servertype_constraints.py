from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('serverdb', '0021_serverinetattribute_server_inet_attribute_value_idx'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE attribute "
                "DROP CONSTRAINT IF EXISTS"
                "  attribute_target_servertype_id_check"
            ),
            reverse_sql=(
                "ALTER TABLE attribute ADD CONSTRAINT"
                "  attribute_target_servertype_id_check "
                "CHECK((type IN ('domain', 'supernet', 'relation')) = "
                "(target_servertype_id IS NOT NULL OR type = 'relation'))"
            ),
        ),
    ]
