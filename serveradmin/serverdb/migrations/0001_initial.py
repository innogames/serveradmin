# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import netfields.fields
import django.utils.timezone
from django.conf import settings
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Attribute',
            fields=[
                ('attribute_id', models.CharField(max_length=32, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]*\\Z', 'Invalid id')], serialize=False, primary_key=True)),
                ('type', models.CharField(choices=[('string', 'string'), ('boolean', 'boolean'), ('hostname', 'hostname'), ('reverse_hostname', 'reverse_hostname'), ('number', 'number'), ('inet', 'inet'), ('macaddr', 'macaddr'), ('date', 'date'), ('supernet', 'supernet')], max_length=32)),
                ('multi', models.BooleanField(default=False)),
                ('hovertext', models.TextField(blank=True, default='')),
                ('group', models.CharField(max_length=32, default='other')),
                ('help_link', models.CharField(blank=True, max_length=255, null=True)),
                ('readonly', models.BooleanField(default=False)),
                ('_reversed_attribute', models.ForeignKey(db_index=False, null=True, to='serverdb.Attribute', blank=True, db_column='reversed_attribute_id', related_name='reversed_attribute_set')),
            ],
            options={
                'db_table': 'attribute',
                'ordering': ('pk',),
            },
        ),
        migrations.CreateModel(
            name='Change',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('change_on', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('changes_json', models.TextField()),
                ('app', models.ForeignKey(null=True, to='apps.Application', on_delete=django.db.models.deletion.PROTECT)),
                ('user', models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name='ChangeAdd',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('server_id', models.IntegerField(db_index=True)),
                ('attributes_json', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='ChangeCommit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('change_on', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('app', models.ForeignKey(null=True, to='apps.Application', on_delete=django.db.models.deletion.PROTECT)),
                ('user', models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name='ChangeDelete',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('server_id', models.IntegerField(db_index=True)),
                ('attributes_json', models.TextField()),
                ('commit', models.ForeignKey(to='serverdb.ChangeCommit')),
            ],
        ),
        migrations.CreateModel(
            name='ChangeUpdate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('server_id', models.IntegerField(db_index=True)),
                ('updates_json', models.TextField()),
                ('commit', models.ForeignKey(to='serverdb.ChangeCommit')),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('project_id', models.CharField(max_length=32, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]*\\Z', 'Invalid id')], serialize=False, primary_key=True)),
                ('subdomain', models.CharField(max_length=16, validators=[django.core.validators.RegexValidator('\\A([a-z0-9]+[\\.\\-])*[a-z0-9]+\\Z', 'Invalid hostname')], unique=True)),
                ('responsible_admin', models.ForeignKey(db_index=False, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'project',
                'ordering': ('pk',),
            },
        ),
        migrations.CreateModel(
            name='Server',
            fields=[
                ('server_id', models.AutoField(primary_key=True, serialize=False)),
                ('hostname', models.CharField(max_length=64, validators=[django.core.validators.RegexValidator('\\A([a-z0-9]+[\\.\\-])*[a-z0-9]+\\Z', 'Invalid hostname')], unique=True)),
                ('intern_ip', netfields.fields.InetAddressField(blank=True, max_length=39, null=True)),
                ('_project', models.ForeignKey(to='serverdb.Project', on_delete=django.db.models.deletion.PROTECT, db_column='project_id')),
            ],
            options={
                'db_table': 'server',
            },
        ),
        migrations.CreateModel(
            name='ServerBooleanAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('_attribute', models.ForeignKey(db_index=False, db_column='attribute_id', to='serverdb.Attribute')),
                ('server', models.ForeignKey(db_index=False, to='serverdb.Server')),
            ],
            options={
                'db_table': 'server_boolean_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerDateAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('value', models.DateField()),
                ('_attribute', models.ForeignKey(db_index=False, db_column='attribute_id', to='serverdb.Attribute')),
                ('server', models.ForeignKey(db_index=False, to='serverdb.Server')),
            ],
            options={
                'db_table': 'server_date_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerHostnameAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('_attribute', models.ForeignKey(db_index=False, db_column='attribute_id', to='serverdb.Attribute')),
                ('server', models.ForeignKey(db_index=False, to='serverdb.Server')),
                ('value', models.ForeignKey(db_index=False, db_column='value', to='serverdb.Server', related_query_name='hostname_attribute_server', on_delete=django.db.models.deletion.PROTECT, related_name='hostname_attribute_servers')),
            ],
            options={
                'db_table': 'server_hostname_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerInetAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('value', netfields.fields.InetAddressField(max_length=39)),
                ('_attribute', models.ForeignKey(db_index=False, db_column='attribute_id', to='serverdb.Attribute')),
                ('server', models.ForeignKey(db_index=False, to='serverdb.Server')),
            ],
            options={
                'db_table': 'server_inet_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerMACAddressAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('value', netfields.fields.MACAddressField()),
                ('_attribute', models.ForeignKey(db_index=False, db_column='attribute_id', to='serverdb.Attribute')),
                ('server', models.ForeignKey(db_index=False, to='serverdb.Server')),
            ],
            options={
                'db_table': 'server_macaddr_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerNumberAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('value', models.DecimalField(max_digits=65, decimal_places=0)),
                ('_attribute', models.ForeignKey(db_index=False, db_column='attribute_id', to='serverdb.Attribute')),
                ('server', models.ForeignKey(db_index=False, to='serverdb.Server')),
            ],
            options={
                'db_table': 'server_number_attribute',
            },
        ),
        migrations.CreateModel(
            name='ServerStringAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('value', models.CharField(max_length=1024)),
                ('_attribute', models.ForeignKey(db_index=False, db_column='attribute_id', to='serverdb.Attribute')),
                ('server', models.ForeignKey(db_index=False, to='serverdb.Server')),
            ],
            options={
                'db_table': 'server_string_attribute',
            },
        ),
        migrations.CreateModel(
            name='Servertype',
            fields=[
                ('servertype_id', models.CharField(max_length=32, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]*\\Z', 'Invalid id')], serialize=False, primary_key=True)),
                ('description', models.CharField(max_length=1024)),
                ('ip_addr_type', models.CharField(choices=[('null', 'null'), ('host', 'host'), ('loadbalancer', 'loadbalancer'), ('network', 'network')], max_length=32)),
                ('_fixed_project', models.ForeignKey(db_index=False, null=True, to='serverdb.Project', blank=True, db_column='fixed_project_id', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
                'db_table': 'servertype',
                'ordering': ('pk',),
            },
        ),
        migrations.CreateModel(
            name='ServertypeAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('required', models.BooleanField(default=False)),
                ('default_value', models.CharField(blank=True, max_length=255, null=True)),
                ('regexp', models.CharField(blank=True, max_length=255, null=True)),
                ('default_visible', models.BooleanField(default=False)),
                ('_attribute', models.ForeignKey(db_index=False, to='serverdb.Attribute', db_column='attribute_id', related_name='servertype_attributes')),
                ('_related_via_attribute', models.ForeignKey(db_index=False, null=True, to='serverdb.Attribute', blank=True, db_column='related_via_attribute_id', related_name='related_via_servertype_attributes')),
                ('_servertype', models.ForeignKey(db_index=False, to='serverdb.Servertype', db_column='servertype_id', related_name='attributes')),
            ],
            options={
                'db_table': 'servertype_attribute',
            },
        ),
        migrations.AddField(
            model_name='server',
            name='_servertype',
            field=models.ForeignKey(to='serverdb.Servertype', on_delete=django.db.models.deletion.PROTECT, db_column='servertype_id'),
        ),
        migrations.AddField(
            model_name='changeadd',
            name='commit',
            field=models.ForeignKey(to='serverdb.ChangeCommit'),
        ),
        migrations.AddField(
            model_name='attribute',
            name='_target_servertype',
            field=models.ForeignKey(db_index=False, null=True, to='serverdb.Servertype', blank=True, db_column='target_servertype_id'),
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
            name='serverhostnameattribute',
            unique_together=set([('server', '_attribute', 'value')]),
        ),
        migrations.AlterIndexTogether(
            name='serverhostnameattribute',
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
