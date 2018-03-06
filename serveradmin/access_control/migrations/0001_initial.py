# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('apps', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessControlGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('name', models.CharField(max_length=80, unique=True)),
                ('query', models.CharField(max_length=1000)),
                ('applications', models.ManyToManyField(related_name='access_control_groups', blank=True, to='apps.Application')),
                ('members', models.ManyToManyField(related_name='access_control_groups', blank=True, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'access_control_group',
            },
        ),
    ]
