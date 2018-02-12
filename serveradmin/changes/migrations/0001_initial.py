# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Addition',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('server_id', models.IntegerField(db_index=True)),
                ('attributes_json', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Commit',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('change_on', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('app', models.ForeignKey(to='apps.Application', on_delete=django.db.models.deletion.PROTECT, null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Deletion',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('server_id', models.IntegerField(db_index=True)),
                ('attributes_json', models.TextField()),
                ('commit', models.ForeignKey(to='changes.Commit')),
            ],
        ),
        migrations.CreateModel(
            name='Modification',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('server_id', models.IntegerField(db_index=True)),
                ('updates_json', models.TextField()),
                ('commit', models.ForeignKey(to='changes.Commit')),
            ],
        ),
        migrations.AddField(
            model_name='addition',
            name='commit',
            field=models.ForeignKey(to='changes.Commit'),
        ),
        migrations.AlterUniqueTogether(
            name='modification',
            unique_together=set([('commit', 'server_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='deletion',
            unique_together=set([('commit', 'server_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='addition',
            unique_together=set([('commit', 'server_id')]),
        ),
    ]
