# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Application',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=80, unique=True)),
                ('app_id', models.CharField(editable=False, max_length=64, unique=True)),
                ('auth_token', models.CharField(editable=False, max_length=64, unique=True)),
                ('location', models.CharField(max_length=150)),
                ('disabled', models.BooleanField(default=False)),
                ('superuser', models.BooleanField(default=False)),
                ('allowed_methods', models.TextField(blank=True)),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
