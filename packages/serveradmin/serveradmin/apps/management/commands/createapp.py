"""Serveradmin

Create application for user

Copyright (c) 2021 InnoGames GmbH
"""
from os import environ

from django.contrib.auth.models import User
from django.core.management import BaseCommand, CommandError

from serveradmin.apps.models import Application


class Command(BaseCommand):
    help = 'Create application for user'

    def add_arguments(self, parser):
        parser.add_argument('--owner', help='Username of application owner')
        parser.add_argument('--superuser', action='store_true',
                            help='Create superuser token')
        parser.add_argument('--non-interactive', action='store_true', help=(
            'Gather values from SERVERADMIN_TOKEN_OWNER, SERVERADMIN_TOKEN '
            'and SERVERADMIN_TOKEN_SUPERUSER env variables. '
            'Any value for SERVERADMIN_TOKEN_SUPERUSER means yes. '
            'Empty string or absence means no.'
        ))

    def handle(self, *args, **options):
        if options['non_interactive']:
            owner = environ.get('SERVERADMIN_TOKEN_OWNER')
            token = environ.get('SERVERADMIN_TOKEN', default='').strip()
            superuser = bool(
                environ.get('SERVERADMIN_TOKEN_SUPERUSER', default=False))
        else:
            if options['owner']:
                owner = options['owner']
            else:
                owner = input('Username of application owner (must exist!): ')

            token = input('Token (empty for auto generated one): ').strip()
            superuser = options['superuser']

        user = User.objects.filter(username=owner)
        if not user.exists():
            raise CommandError(f'No such user {owner} found!')

        app = Application.objects.filter(
            owner=user.get(), name=f'default app for {owner}')
        if app.exists():
            self.stdout.write(self.style.WARNING(
                f'Default app for {owner} already exists - skipping.'))
            return

        app = Application()
        app.name = f'default app for {owner}'
        app.owner = user.get()
        app.superuser = superuser
        if token:
            app.auth_token = token
        app.save()
