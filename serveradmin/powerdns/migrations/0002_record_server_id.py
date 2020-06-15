# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-06-23 11:37
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('powerdns', '0001_powerdns_default_schema'),
    ]

    operations = [
        migrations.RunSQL(sql="""            
            ALTER TABLE records ADD column record_id INT DEFAULT NULL;
            ALTER TABLE records ADD column object_id INT DEFAULT NULL;
        """, reverse_sql="""
            ALTER TABLE records DROP column IF EXISTS record_id;
            ALTER TABLE records DROP column IF EXISTS object_id;
        """)
    ]