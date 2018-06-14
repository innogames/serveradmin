# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
import django.core.validators
from django.conf import settings
import netfields.fields
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('apps', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Attribute',
            fields=[
                ('attribute_id', models.CharField(primary_key=True, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]+\\Z', 'Invalid id')], serialize=False, max_length=32)),
                ('type', models.CharField(choices=[
                    ('string', 'string'),
                    ('boolean', 'boolean'),
                    ('relation', 'relation'),
                    ('reverse', 'reverse'),
                    ('number', 'number'),
                    ('inet', 'inet'),
                    ('macaddr', 'macaddr'),
                    ('date', 'date'),
                    ('supernet', 'supernet'),
                ], max_length=32)),
                ('multi', models.BooleanField(default=False)),
                ('hovertext', models.TextField(default='', blank=True)),
                ('group', models.CharField(default='other', max_length=32)),
                ('help_link', models.CharField(null=True, blank=True, max_length=255)),
                ('readonly', models.BooleanField(default=False)),
                ('_reversed_attribute', models.ForeignKey(related_name='reversed_attribute_set', db_column='reversed_attribute_id', to='serverdb.Attribute', blank=True, null=True, db_index=False)),
            ],
            options={
                'ordering': ('pk',),
                'db_table': 'attribute',
            },
        ),
        migrations.CreateModel(
            name='Change',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_on', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('changes_json', models.TextField()),
                ('app', models.ForeignKey(to='apps.Application', on_delete=django.db.models.deletion.PROTECT, null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ChangeAdd',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('server_id', models.IntegerField(db_index=True)),
                ('attributes_json', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='ChangeCommit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_on', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('app', models.ForeignKey(to='apps.Application', on_delete=django.db.models.deletion.PROTECT, null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ChangeDelete',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('server_id', models.IntegerField(db_index=True)),
                ('attributes_json', models.TextField()),
                ('commit', models.ForeignKey(to='serverdb.ChangeCommit')),
            ],
        ),
        migrations.CreateModel(
            name='ChangeUpdate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('server_id', models.IntegerField(db_index=True)),
                ('updates_json', models.TextField()),
                ('commit', models.ForeignKey(to='serverdb.ChangeCommit')),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('project_id', models.CharField(primary_key=True, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]+\\Z', 'Invalid id')], serialize=False, max_length=32)),
                ('subdomain', models.CharField(validators=[django.core.validators.RegexValidator('\\A([a-z0-9]+[\\.\\-])*[a-z0-9]+\\Z', 'Invalid hostname')], unique=True, max_length=16)),
                ('responsible_admin', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, db_index=False)),
            ],
            options={
                'ordering': ('pk',),
                'db_table': 'project',
            },
        ),
        migrations.CreateModel(
            name='Server',
            fields=[
                ('server_id', models.AutoField(primary_key=True, serialize=False)),
                ('hostname', models.CharField(validators=[django.core.validators.RegexValidator('\\A([a-z0-9]+[\\.\\-])*[a-z0-9]+\\Z', 'Invalid hostname')], unique=True, max_length=64)),
                ('intern_ip', netfields.fields.InetAddressField(null=True, blank=True, max_length=39)),
                ('_project', models.ForeignKey(db_column='project_id', to='serverdb.Project', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
                'db_table': 'server',
            },
        ),
        migrations.CreateModel(
            name='ServerBooleanAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('_attribute', models.ForeignKey(db_column='attribute_id', to='serverdb.Attribute', db_index=False)),
                ('server', models.ForeignKey(to='serverdb.Server', db_index=False)),
            ],
            options={
                'db_table': 'server_boolean_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerDateAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.DateField()),
                ('_attribute', models.ForeignKey(db_column='attribute_id', to='serverdb.Attribute', db_index=False)),
                ('server', models.ForeignKey(to='serverdb.Server', db_index=False)),
            ],
            options={
                'db_table': 'server_date_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerRelationAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('_attribute', models.ForeignKey(db_column='attribute_id', to='serverdb.Attribute', db_index=False)),
                ('server', models.ForeignKey(to='serverdb.Server', db_index=False)),
                ('value', models.ForeignKey(related_name='relation_attribute_servers', db_column='value', to='serverdb.Server', on_delete=django.db.models.deletion.PROTECT, db_index=False, related_query_name='relation_attribute_server')),
            ],
            options={
                'db_table': 'server_relation_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerInetAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', netfields.fields.InetAddressField(max_length=39)),
                ('_attribute', models.ForeignKey(db_column='attribute_id', to='serverdb.Attribute', db_index=False)),
                ('server', models.ForeignKey(to='serverdb.Server', db_index=False)),
            ],
            options={
                'db_table': 'server_inet_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerMACAddressAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', netfields.fields.MACAddressField()),
                ('_attribute', models.ForeignKey(db_column='attribute_id', to='serverdb.Attribute', db_index=False)),
                ('server', models.ForeignKey(to='serverdb.Server', db_index=False)),
            ],
            options={
                'db_table': 'server_macaddr_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerNumberAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.DecimalField(max_digits=65, decimal_places=0)),
                ('_attribute', models.ForeignKey(db_column='attribute_id', to='serverdb.Attribute', db_index=False)),
                ('server', models.ForeignKey(to='serverdb.Server', db_index=False)),
            ],
            options={
                'db_table': 'server_number_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerStringAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=1024)),
                ('_attribute', models.ForeignKey(db_column='attribute_id', to='serverdb.Attribute', db_index=False)),
                ('server', models.ForeignKey(to='serverdb.Server', db_index=False)),
            ],
            options={
                'db_table': 'server_string_attribute',
            },
        ),
        migrations.CreateModel(
            name='Servertype',
            fields=[
                ('servertype_id', models.CharField(primary_key=True, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]+\\Z', 'Invalid id')], serialize=False, max_length=32)),
                ('description', models.CharField(max_length=1024)),
                ('ip_addr_type', models.CharField(choices=[('null', 'null'), ('host', 'host'), ('loadbalancer', 'loadbalancer'), ('network', 'network')], max_length=32)),
            ],
            options={
                'ordering': ('pk',),
                'db_table': 'servertype',
            },
        ),
        migrations.CreateModel(
            name='ServertypeAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('required', models.BooleanField(default=False)),
                ('default_value', models.CharField(null=True, blank=True, max_length=255)),
                ('regexp', models.CharField(null=True, blank=True, max_length=255)),
                ('default_visible', models.BooleanField(default=False)),
                ('_attribute', models.ForeignKey(related_name='servertype_attributes', db_column='attribute_id', to='serverdb.Attribute', db_index=False)),
                ('_related_via_attribute', models.ForeignKey(related_name='related_via_servertype_attributes', db_column='related_via_attribute_id', to='serverdb.Attribute', blank=True, null=True, db_index=False)),
                ('_servertype', models.ForeignKey(related_name='attributes', db_column='servertype_id', to='serverdb.Servertype', db_index=False)),
            ],
            options={
                'db_table': 'servertype_attribute',
            },
        ),
        migrations.AddField(
            model_name='server',
            name='_servertype',
            field=models.ForeignKey(db_column='servertype_id', to='serverdb.Servertype', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='changeadd',
            name='commit',
            field=models.ForeignKey(to='serverdb.ChangeCommit'),
        ),
        migrations.AddField(
            model_name='attribute',
            name='_target_servertype',
            field=models.ForeignKey(db_column='target_servertype_id', to='serverdb.Servertype', blank=True, null=True, db_index=False),
        ),
        migrations.AlterUniqueTogether(
            name='servertypeattribute',
            unique_together=set([('_servertype', '_attribute')]),
        ),
        migrations.AlterUniqueTogether(
            name='serverstringattribute',
            unique_together=set([('server', '_attribute', 'value')]),
        ),
        migrations.AlterIndexTogether(
            name='serverstringattribute',
            index_together=set([('_attribute', 'value')]),
        ),
        migrations.AlterUniqueTogether(
            name='servernumberattribute',
            unique_together=set([('server', '_attribute', 'value')]),
        ),
        migrations.AlterIndexTogether(
            name='servernumberattribute',
            index_together=set([('_attribute', 'value')]),
        ),
        migrations.AlterUniqueTogether(
            name='servermacaddressattribute',
            unique_together=set([('server', '_attribute', 'value')]),
        ),
        migrations.AlterIndexTogether(
            name='servermacaddressattribute',
            index_together=set([('_attribute', 'value')]),
        ),
        migrations.AlterUniqueTogether(
            name='serverinetattribute',
            unique_together=set([('server', '_attribute', 'value')]),
        ),
        migrations.AlterIndexTogether(
            name='serverinetattribute',
            index_together=set([('_attribute', 'value')]),
        ),
        migrations.AlterUniqueTogether(
            name='serverrelationattribute',
            unique_together=set([('server', '_attribute', 'value')]),
        ),
        migrations.AlterIndexTogether(
            name='serverrelationattribute',
            index_together=set([('_attribute', 'value')]),
        ),
        migrations.AlterUniqueTogether(
            name='serverdateattribute',
            unique_together=set([('server', '_attribute', 'value')]),
        ),
        migrations.AlterIndexTogether(
            name='serverdateattribute',
            index_together=set([('_attribute', 'value')]),
        ),
        migrations.AlterUniqueTogether(
            name='serverbooleanattribute',
            unique_together=set([('server', '_attribute')]),
        ),
        migrations.AlterIndexTogether(
            name='serverbooleanattribute',
            index_together=set([('_attribute',)]),
        ),
        migrations.AlterUniqueTogether(
            name='changeupdate',
            unique_together=set([('commit', 'server_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='changedelete',
            unique_together=set([('commit', 'server_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='changeadd',
            unique_together=set([('commit', 'server_id')]),
        ),
    ]
