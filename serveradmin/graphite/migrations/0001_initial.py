# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Collection',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('name', models.CharField(max_length=255, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]+\\Z', 'Invalid id')])),
                ('params', models.TextField(blank=True, help_text='\n        Part of the URL after "?" to GET the graph or the value from\n        the Graphite.  It will be concatenated with the params for\n        the template and the variation.  Make sure it doesn\'t include\n        any character that doesn\'t allowed on URL\'s.  Also do not include "?"\n        and do not put "&" at the end.\n\n        The params can include variables inside curly brackets like\n        "{hostname}".\n        Variables can be any string attribute except multiple ones related to\n        the servers.  See Python String Formatting documentation [1] for other\n        formatting options.  The dots inside the values are replaced with\n        underscores in advance.  If you need to include a brace character in\n        the parameters, it can be escaped by doubling: \'{{ and }}\'.\n\n        Example params:\n\n            width=500&height=500\n\n        [1] https://docs.python.org/2/library/string.html#formatstrings\n        ')),
                ('sort_order', models.FloatField(default=0)),
                ('overview', models.BooleanField(help_text="\n        Marks the collection to be shown on the overview page.  For\n        the overview page, sprites will be generated and cached on\n        the server in advance to improve the loading time.  width=150&height=100&graphOnly=true will be\n        appended to generated URL's to get the images for overview.\n        ", default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'graphite_collection',
                'ordering': ['sort_order'],
            },
        ),
        migrations.CreateModel(
            name='Numeric',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('params', models.TextField(blank=True, help_text='Same as the params of the collections')),
                ('sort_order', models.FloatField(default=0)),
                ('attribute', models.ForeignKey(to='serverdb.Attribute')),
                ('collection', models.ForeignKey(to='graphite.Collection')),
            ],
            options={
                'db_table': 'graphite_numeric',
                'ordering': ['sort_order'],
            },
        ),
        migrations.CreateModel(
            name='Relation',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('sort_order', models.FloatField(default=0)),
                ('attribute', models.ForeignKey(to='serverdb.Attribute')),
                ('collection', models.ForeignKey(to='graphite.Collection')),
            ],
            options={
                'db_table': 'graphite_relation',
                'ordering': ['sort_order'],
            },
        ),
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('name', models.CharField(max_length=255, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]+\\Z', 'Invalid id')])),
                ('params', models.TextField(blank=True, help_text='\n        Same as the params of the collections.\n        ')),
                ('sort_order', models.FloatField(default=0)),
                ('description', models.TextField(blank=True)),
                ('foreach_path', models.CharField(blank=True, help_text='\n        Generates multiple graphs from the same template.  Variables can be\n        used like "params".  It will be a variable for the "params" that can\n        be used as {foreach_id}.  Example value:\n\n            servers.{hostname}.system.cpu.*\n        ', max_length=256)),
                ('collection', models.ForeignKey(to='graphite.Collection')),
            ],
            options={
                'db_table': 'graphite_template',
                'ordering': ['sort_order'],
            },
        ),
        migrations.CreateModel(
            name='Variation',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('name', models.CharField(max_length=255, validators=[django.core.validators.RegexValidator('\\A[a-z][a-z0-9_]+\\Z', 'Invalid id')])),
                ('params', models.TextField(blank=True, help_text='\n        Same as the params of the collections.\n        ')),
                ('sort_order', models.FloatField(default=0)),
                ('summarize_interval', models.CharField(max_length=255, help_text='\n        Interval string that makes sense to use on the summarize() function on\n        the Graphite for this variation.  It can be used in the params as\n        {summarize_interval}.\n        ')),
                ('collection', models.ForeignKey(to='graphite.Collection')),
            ],
            options={
                'db_table': 'graphite_variation',
                'ordering': ['sort_order'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='collection',
            unique_together=set([('name', 'overview')]),
        ),
        migrations.AlterUniqueTogether(
            name='variation',
            unique_together=set([('collection', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='template',
            unique_together=set([('collection', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='relation',
            unique_together=set([('collection', 'attribute')]),
        ),
        migrations.AlterUniqueTogether(
            name='numeric',
            unique_together=set([('collection', 'attribute')]),
        ),
    ]
