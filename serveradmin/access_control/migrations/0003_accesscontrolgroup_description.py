# Generated by Django 3.2.16 on 2022-10-12 10:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('access_control', '0002_whitelist_blacklist_toggle'),
    ]

    operations = [
        migrations.AddField(
            model_name='accesscontrolgroup',
            name='description',
            field=models.TextField(blank=True),
        ),
    ]
