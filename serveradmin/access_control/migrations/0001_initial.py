# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('apps', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessControlGroup',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, unique=True)),
                ('create_server_query', models.CharField(max_length=1000)),
                ('edit_server_query', models.CharField(max_length=1000)),
                ('commit_server_query', models.CharField(max_length=1000)),
                ('delete_server_query', models.CharField(max_length=1000)),
                ('applications', models.ManyToManyField(blank=True, to='apps.Application', related_name='access_control_groups')),
                ('members', models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL, related_name='access_control_groups')),
            ],
            options={
                'db_table': 'access_control_group',
            },
        ),
    ]
