# Generated by Django 3.2.18 on 2023-03-02 09:12

from django.db import migrations, models
import serveradmin.serverdb.models


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0014_delete_deprecated_change_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='attribute',
            name='history',
            field=models.BooleanField(default=True, help_text='Log changes to this attribute')
        ),
    ]
