# Generated by Django 3.2.23 on 2023-12-18 13:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('powerdns', '0006_alter_recordsetting_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recordsetting',
            name='record_type',
            field=models.CharField(choices=[('A_AAAA', 'A/AAAA'), ('A', 'A'), ('AAAA', 'AAAA'), ('CNAME', 'CNAME'), ('MX', 'MX'), ('NS', 'NS'), ('PTR', 'PTR'), ('SSHFP', 'SSHFP'), ('SOA', 'SOA'), ('SRV', 'SRV'), ('TXT', 'TXT')], max_length=8),
        ),
    ]
