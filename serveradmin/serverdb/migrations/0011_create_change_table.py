# Generated by Django 3.2.16 on 2022-10-24 13:37

from django.db import migrations, models
import django.db.models.deletion

import serveradmin


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0010_delete_change'),
    ]

    operations = [
        migrations.CreateModel(
            name='Change',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.IntegerField(db_index=True)),
                ('change_type', models.CharField(choices=[('create', 'create'), ('change', 'change'), ('delete', 'delete')], max_length=6)),
                ('change_json', models.JSONField(encoder=serveradmin.serverdb.models.Change.ChangeJSONEncoder)),
                ('commit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='serverdb.changecommit')),
            ],
        ),
    ]
