# Generated by Django 4.2.23 on 2025-07-01 09:27

import django.contrib.postgres.indexes
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0020_alter_servertype_ip_addr_type'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='serverinetattribute',
            index=django.contrib.postgres.indexes.GistIndex(fields=['value'], name='server_inet_attribute_value_idx', opclasses=['inet_ops']),
        ),
    ]
