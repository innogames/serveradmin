"""Serveradmin - Tests for optional application auth tokens

Copyright (c) 2026 InnoGames GmbH
"""
from io import StringIO
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import RequestFactory, TestCase

from adminapi.request import calc_app_id, calc_security_token
from serveradmin.api.decorators import authenticate_app_psk
from serveradmin.apps.admin import ApplicationAdmin
from serveradmin.apps.models import Application


class ApplicationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice')

    def _create(self, name, **kwargs):
        return Application.objects.create(
            name=name, owner=self.user, location='', **kwargs
        )

    def test_no_token_by_default(self):
        app = self._create('app')

        self.assertIsNone(app.auth_token)
        self.assertIsNone(app.app_id)

    def test_app_id_derived_from_token(self):
        app = self._create('app', auth_token='secret')

        self.assertEqual('secret', app.auth_token)
        self.assertEqual(calc_app_id('secret'), app.app_id)

    def test_empty_token_is_stored_as_null(self):
        app = self._create('app', auth_token='')

        app.refresh_from_db()
        self.assertIsNone(app.auth_token)
        self.assertIsNone(app.app_id)

    def test_multiple_apps_without_token_can_coexist(self):
        self._create('app-a')
        self._create('app-b')
        self._create('app-c', auth_token='')

        self.assertEqual(3, Application.objects.filter(
            auth_token__isnull=True, app_id__isnull=True
        ).count())

    def test_clearing_token_clears_app_id(self):
        app = self._create('app', auth_token='secret')

        app.auth_token = None
        app.save()

        app.refresh_from_db()
        self.assertIsNone(app.auth_token)
        self.assertIsNone(app.app_id)


class AuthenticatePskTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice')
        self.timestamp = '1700000000'
        self.body = '{"hostname": "test0"}'

    def test_app_without_token_is_denied(self):
        app = Application.objects.create(
            name='app', owner=self.user, location=''
        )
        # Simulate a database row with an app_id but no token, e.g. edited
        # by hand. The authentication must not crash on a None token.
        Application.objects.filter(pk=app.pk).update(app_id='orphan')

        with self.assertRaisesMessage(
            PermissionDenied, 'Application has no auth token'
        ):
            authenticate_app_psk(
                'orphan',
                calc_security_token('anything', self.timestamp, self.body),
                self.timestamp,
                self.body,
            )

    def test_unknown_app_id_is_denied(self):
        with self.assertRaises(PermissionDenied):
            authenticate_app_psk(
                'unknown', 'token', self.timestamp, self.body
            )

    def test_app_with_token_authenticates(self):
        app = Application.objects.create(
            name='app', owner=self.user, location='', auth_token='secret'
        )

        authenticated = authenticate_app_psk(
            app.app_id,
            calc_security_token('secret', self.timestamp, self.body),
            self.timestamp,
            self.body,
        )

        self.assertEqual(app, authenticated)

    def test_wrong_token_is_denied(self):
        app = Application.objects.create(
            name='app', owner=self.user, location='', auth_token='secret'
        )

        with self.assertRaisesMessage(
            PermissionDenied, 'Invalid security token'
        ):
            authenticate_app_psk(
                app.app_id,
                calc_security_token('wrong', self.timestamp, self.body),
                self.timestamp,
                self.body,
            )


class ApplicationAdminActionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice')
        self.admin = ApplicationAdmin(Application, AdminSite())
        self.request = RequestFactory().post('/admin/apps/application/')
        self.request.user = self.user
        self.with_token = Application.objects.create(
            name='with-token', owner=self.user, location='',
            auth_token='secret',
        )
        self.without_token = Application.objects.create(
            name='without-token', owner=self.user, location='',
        )

    def test_generate_only_for_apps_without_token(self):
        with patch.object(self.admin, 'message_user'):
            self.admin.generate_auth_token(
                self.request, Application.objects.all()
            )

        self.with_token.refresh_from_db()
        self.without_token.refresh_from_db()
        self.assertEqual('secret', self.with_token.auth_token)
        self.assertIsNotNone(self.without_token.auth_token)
        self.assertEqual(
            calc_app_id(self.without_token.auth_token),
            self.without_token.app_id,
        )

    def test_revoke_clears_token_and_app_id(self):
        with patch.object(self.admin, 'message_user'):
            self.admin.revoke_auth_token(
                self.request, Application.objects.all()
            )

        self.with_token.refresh_from_db()
        self.without_token.refresh_from_db()
        self.assertIsNone(self.with_token.auth_token)
        self.assertIsNone(self.with_token.app_id)
        self.assertIsNone(self.without_token.auth_token)


class CreateAppCommandTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice')

    def _call(self, env):
        out = StringIO()
        with patch.dict('os.environ', env, clear=False):
            call_command('createapp', non_interactive=True, stdout=out)
        return out.getvalue()

    def test_generates_token_when_none_given(self):
        output = self._call({
            'SERVERADMIN_TOKEN_OWNER': 'alice',
            'SERVERADMIN_TOKEN': '',
        })

        app = Application.objects.get(name='default app for alice')
        self.assertIsNotNone(app.auth_token)
        self.assertEqual(calc_app_id(app.auth_token), app.app_id)
        self.assertIn(app.auth_token, output)

    def test_uses_given_token(self):
        output = self._call({
            'SERVERADMIN_TOKEN_OWNER': 'alice',
            'SERVERADMIN_TOKEN': 'secret',
            'SERVERADMIN_TOKEN_SUPERUSER': 'yes',
        })

        app = Application.objects.get(name='default app for alice')
        self.assertEqual('secret', app.auth_token)
        self.assertTrue(app.superuser)
        self.assertNotIn('secret', output)
