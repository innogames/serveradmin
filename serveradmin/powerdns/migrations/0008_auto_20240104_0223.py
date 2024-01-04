# Generated by Django 3.2.23 on 2024-01-04 08:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0017_alter_server_hostname'),
        ('powerdns', '0007_alter_recordsetting_record_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='recordsetting',
            name='ttl',
            field=models.IntegerField(default=3600),
        ),
        migrations.AlterField(
            model_name='recordsetting',
            name='domain',
            field=models.ForeignKey(blank=True, limit_choices_to={'type': 'relation'}, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='serverdb.attribute'),
        ),
    ]
