# Generated by Django 3.2.11 on 2022-01-24 09:55

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Domain',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('master', models.CharField(default=None, max_length=128)),
                ('type', models.CharField(choices=[('MASTER', 'MASTER'), ('SLAVE', 'SLAVE'), ('NATIVE', 'NATIVE')], max_length=6)),
            ],
            options={
                'db_table': 'domains',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Record',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(default=None, max_length=255)),
                ('type', models.CharField(choices=[('A', 'A'), ('AAAA', 'AAAA'), ('CNAME', 'CNAME'), ('TXT', 'TXT'), ('SSHFP', 'SSHFP'), ('SOA', 'SOA'), ('MX', 'MX'), ('PTR', 'PTR'), ('NS', 'NS')], default=None, max_length=10)),
                ('content', models.CharField(default=None, max_length=65535)),
                ('ttl', models.IntegerField()),
            ],
            options={
                'db_table': 'records',
                'managed': False,
            },
        ),
    ]
