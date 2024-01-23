# Generated by Django 3.2.23 on 2024-01-04 08:23

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0016_optional_servertype_for_relation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='server',
            name='hostname',
            field=models.CharField(max_length=254, unique=True, validators=[django.core.validators.RegexValidator('\\A(\\*\\.)?([a-z0-9_]+(\\.|-+))*[a-z0-9]+\\Z', 'Invalid hostname')]),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE server "
                "DROP CONSTRAINT server_hostname_check, "
                "ADD CONSTRAINT server_hostname_check "
                "CHECK (hostname::text ~ '\A(\*\.)?([a-z0-9_]+(\.|-+))*[a-z0-9]+\Z'::text);"
            ),
            reverse_sql=(
                "ALTER TABLE server "
                "DROP CONSTRAINT server_hostname_check, "
                "ADD CONSTRAINT server_hostname_check "
                "CHECK (hostname::text ~ '\A(\*\.)?([a-z0-9]+(\.|-+))*[a-z0-9]+\Z'::text);"
            )
        ),
    ]
