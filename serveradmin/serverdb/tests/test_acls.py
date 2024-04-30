from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TransactionTestCase

from serveradmin.access_control.models import AccessControlGroup
from serveradmin.apps.models import Application
from serveradmin.dataset import Query
from serveradmin.serverdb import query_committer
from serveradmin.serverdb.models import Attribute


class ACLTestCase(TransactionTestCase):
    """Test Permissions are evaluated properly

    Some of the tests might be a redundant but since the amount of test cases
    is manageable, and we really want to be sure here that the ACLs behave as
    we expect them we just test most of them instead of just a few.

    """

    fixtures = ['auth_user.json', 'test_dataset.json']

    def test_deny_if_not_authenticated(self):
        with self.assertRaises(PermissionDenied) as error:
            # Trying to commit without being authenticated must not be possible.
            query_committer._access_control(None, None, {}, {}, {}, {})
        self.assertEqual('Missing authentication!', str(error.exception))

    def test_permit_if_superuser_app(self):
        user = User.objects.first()
        app = Application.objects.create(
            name='superuser test',
            app_id='superuser test',
            auth_token='secret',
            owner=user,
            location='test',
        )

        self.assertIsNone(query_committer._access_control(None, app, {}, {}, {}, {}))

    def test_permit_if_superuser(self):
        user = User.objects.first()
        user.is_superuser = True

        self.assertIsNone(query_committer._access_control(user, None, {}, {}, {}, {}))

    def test_deny_if_app_acl_does_not_cover_object(self):
        user = User.objects.first()
        app = Application.objects.create(
            name='superuser test',
            app_id='superuser test',
            auth_token='secret',
            owner=user,
            location='test',
        )
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=vm')
        acl.applications.add(app)
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(None, app, unchanged_objects, {}, changed_objects, {})
        self.assertEqual(
            'Insufficient access rights to object "test0" for application '
            '"superuser test": Object is not covered by ACL "app test", '
            'Attribute "servertype" does not match the filter "\'vm\'".',
            str(error.exception),
        )

    def test_deny_if_user_acl_does_not_cover_object(self):
        user = User.objects.first()
        user.is_superuser = False

        acl = AccessControlGroup.objects.create(name='app test', query='servertype=vm')
        acl.members.add(user)
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(user, None, unchanged_objects, {}, changed_objects, {})
        self.assertEqual(
            'Insufficient access rights to object "test0" for user '
            '"hannah.acker": Object is not covered by ACL "app test", '
            'Attribute "servertype" does not match the filter "\'vm\'".',
            str(error.exception),
        )

    def test_permit_if_app_acl_covers_object(self):
        user = User.objects.first()
        app = Application.objects.create(
            name='superuser test',
            app_id='superuser test',
            auth_token='secret',
            owner=user,
            location='test',
        )
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=False)
        acl.applications.add(app)
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        self.assertIsNone(query_committer._access_control(None, app, unchanged_objects, {}, changed_objects, {}))

    def test_permit_if_user_acl_covers_object(self):
        user = User.objects.first()
        user.is_superuser = False
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=False)
        acl.members.add(user)
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        self.assertIsNone(query_committer._access_control(user, None, unchanged_objects, {}, changed_objects, {}))

    def test_deny_if_app_acl_whitelist_does_not_list_attribute(self):
        user = User.objects.first()
        app = Application.objects.create(
            name='superuser test',
            app_id='superuser test',
            auth_token='secret',
            owner=user,
            location='test',
        )
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=True)
        acl.applications.add(app)
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(None, app, unchanged_objects, {}, changed_objects, {})
        self.assertEqual(
            'Insufficient access rights to object "test0" for application '
            '"superuser test": Change is not covered by ACL "app test", '
            'Attribute "os" was modified despite not beeing whitelisted.',
            str(error.exception),
        )

    def test_deny_if_user_acl_whitelist_does_not_list_attribute(self):
        user = User.objects.first()
        user.is_superuser = False

        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=True)
        acl.members.add(user)
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(user, None, unchanged_objects, {}, changed_objects, {})
        self.assertEqual(
            'Insufficient access rights to object "test0" for user '
            '"hannah.acker": Change is not covered by ACL "app test", '
            'Attribute "os" was modified despite not beeing whitelisted.',
            str(error.exception),
        )

    def test_permit_if_app_acl_whitelist_lists_attribute(self):
        user = User.objects.first()
        app = Application.objects.create(
            name='superuser test',
            app_id='superuser test',
            auth_token='secret',
            owner=user,
            location='test',
        )
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=True)
        acl.applications.add(app)
        acl.attributes.add(Attribute.objects.get(attribute_id='os'))
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        self.assertIsNone(query_committer._access_control(None, app, unchanged_objects, {}, changed_objects, {}))

    def test_permit_if_user_acl_whitelist_lists_attribute(self):
        user = User.objects.first()
        user.is_superuser = False
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=True)
        acl.members.add(user)
        acl.attributes.add(Attribute.objects.get(attribute_id='os'))
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        self.assertIsNone(query_committer._access_control(user, None, unchanged_objects, {}, changed_objects, {}))

    def test_deny_if_app_acl_blacklist_lists_attribute(self):
        user = User.objects.first()
        app = Application.objects.create(
            name='superuser test',
            app_id='superuser test',
            auth_token='secret',
            owner=user,
            location='test',
        )
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=False)
        acl.applications.add(app)
        acl.attributes.add(Attribute.objects.get(attribute_id='os'))
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(None, app, unchanged_objects, {}, changed_objects, {})
        self.assertEqual(
            'Insufficient access rights to object "test0" for application '
            '"superuser test": Change is not covered by ACL "app test", '
            'Attribute "os" was modified despite not beeing whitelisted.',
            str(error.exception),
        )

    def test_deny_if_user_acl_blacklist_lists_attribute(self):
        user = User.objects.first()
        user.is_superuser = False
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=False)
        acl.members.add(user)
        acl.attributes.add(Attribute.objects.get(attribute_id='os'))
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(user, None, unchanged_objects, {}, changed_objects, {})
        self.assertEqual(
            'Insufficient access rights to object "test0" for user '
            '"hannah.acker": Change is not covered by ACL "app test", '
            'Attribute "os" was modified despite not beeing whitelisted.',
            str(error.exception),
        )

    def test_permit_if_app_acl_blacklist_misses_attribute(self):
        user = User.objects.first()
        app = Application.objects.create(
            name='superuser test',
            app_id='superuser test',
            auth_token='secret',
            owner=user,
            location='test',
        )
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=False)
        acl.applications.add(app)
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        self.assertIsNone(query_committer._access_control(None, app, unchanged_objects, {}, changed_objects, {}))

    def test_permit_if_user_acl_blacklist_misses_attribute(self):
        user = User.objects.first()
        user.is_superuser = False
        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=False)
        acl.members.add(user)
        acl.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_objects = {changed_object['object_id']: changed_object}

        self.assertIsNone(query_committer._access_control(user, None, unchanged_objects, {}, changed_objects, {}))

    def test_deny_if_multiple_app_acls_cover_one_object_change_set(self):
        # One ACL must cover all changes made to one object. Changes to one
        # object being covered by multiple ACLs is not allowed.

        user = User.objects.first()
        app = Application.objects.create(
            name='superuser test',
            app_id='superuser test',
            auth_token='secret',
            owner=user,
            location='test',
        )

        acl_1 = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=True)
        acl_1.applications.add(app)
        acl_1.attributes.add(Attribute.objects.get(attribute_id='os'))
        acl_1.save()

        acl_2 = AccessControlGroup.objects.create(name='app test 2', query='servertype=test0', is_whitelist=True)
        acl_2.applications.add(app)
        acl_2.attributes.add(Attribute.objects.get(attribute_id='database'))
        acl_2.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'database', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'database', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_object['database'] = 'bingo'
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(None, app, unchanged_objects, {}, changed_objects, {})
        self.assertEqual(
            'Insufficient access rights to object "test0" for application '
            '"superuser test": Change is not covered by ACL "app test", '
            'Attribute "database" was modified despite not beeing whitelisted.'
            'Change is not covered by ACL "app test 2", Attribute "os" was '
            'modified despite not beeing whitelisted.',
            str(error.exception),
        )

    def test_deny_if_multiple_user_acls_cover_one_object_change_set(self):
        # One ACL must cover all changes made to one object. Changes to one
        # object being covered by multiple ACLs is not allowed.

        user = User.objects.first()
        user.is_superuser = False

        acl_1 = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=True)
        acl_1.members.add(user)
        acl_1.attributes.add(Attribute.objects.get(attribute_id='os'))
        acl_1.save()

        acl_2 = AccessControlGroup.objects.create(name='app test 2', query='servertype=test0', is_whitelist=True)
        acl_1.members.add(user)
        acl_2.attributes.add(Attribute.objects.get(attribute_id='database'))
        acl_2.save()

        unchanged_object = Query({'object_id': 1}, ['os', 'database', 'hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'object_id': 1}, ['os', 'database', 'hostname', 'servertype']).get()
        changed_object['os'] = 'bookworm'
        changed_object['database'] = 'bingo'
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(user, None, unchanged_objects, {}, changed_objects, {})
        self.assertEqual(
            'Insufficient access rights to object "test0" for user '
            '"hannah.acker": Change is not covered by ACL "app test", '
            'Attribute "database" was modified despite not beeing '
            'whitelisted.',
            str(error.exception),
        )

    def test_hijack_objects_not_possible(self):
        # When an application or user is allowed to change certain attributes
        # it must be guaranteed that permission checks are taking place against
        # the status quo and not the new values.

        user = User.objects.first()
        user.is_superuser = False

        acl = AccessControlGroup.objects.create(name='app test', query='servertype=test0', is_whitelist=False)
        acl.members.add(user)
        acl.save()

        unchanged_object = Query({'hostname': 'test2', 'servertype': 'test2'}, ['hostname', 'servertype']).get()
        unchanged_objects = {unchanged_object['object_id']: unchanged_object}

        changed_object = Query({'hostname': 'test2', 'servertype': 'test2'}, ['hostname', 'servertype']).get()
        changed_object['servertype'] = 'test0'  # Attacker attempts to hijack object
        changed_objects = {changed_object['object_id']: changed_object}

        with self.assertRaises(PermissionDenied) as error:
            query_committer._access_control(user, None, unchanged_objects, {}, changed_objects, {})
