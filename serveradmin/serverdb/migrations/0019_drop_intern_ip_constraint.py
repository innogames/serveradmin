# Generated by Django 4.2.11 on 2024-07-24 12:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0018_alter_server_hostname'),
    ]

    operations = [
        migrations.RunSQL("ALTER TABLE server DROP CONSTRAINT IF EXISTS server_inter_ip_exclude"),
    ]
