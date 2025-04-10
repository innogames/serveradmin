# Generated by Django 2.1.1 on 2018-09-02 22:27

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('apps', '__first__'),
        ('serverdb', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessControlGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, unique=True)),
                ('query', models.CharField(max_length=1000)),
                (
                    'applications',
                    models.ManyToManyField(
                        blank=True,
                        limit_choices_to={'disabled': False, 'superuser': False},
                        related_name='access_control_groups',
                        to='apps.Application',
                    ),
                ),
                (
                    'attributes',
                    models.ManyToManyField(blank=True, related_name='access_control_groups', to='serverdb.Attribute'),
                ),
                (
                    'members',
                    models.ManyToManyField(
                        blank=True,
                        limit_choices_to={'is_active': True, 'is_superuser': False},
                        related_name='access_control_groups',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'access_control_group',
            },
        ),
    ]
