"""Serveradmin

When upgraded to Django >= 3.x we can use DJANG_SUPERUSER_* environment
variables together with the createsuperuser command and the --non-interactive
to do this.

Copyright (c) 2021 InnoGames GmbH
"""

from os import environ

from django.contrib.auth.models import User
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create default user based on environment variables'

    def handle(self, *args, **options):
        username = environ.get('DJANGO_SUPERUSER_USERNAME')
        password = environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not all([username, password]):
            raise CommandError('Missing at least one DJANG_SUPERUSER_* env')

        if not User.objects.filter(username=username).exists():
            user = User()
            user.username = username
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()
