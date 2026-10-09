from ipaddress import ip_address

from django.contrib.auth.models import User
from django.test import TransactionTestCase

from adminapi.filters import Any
from serveradmin.dataset import Query
from serveradmin.serverdb.models import Change


class RestoreViewTest(TransactionTestCase):
    fixtures = ['auth_user.json', 'test_dataset.json']

    def setUp(self) -> None:
        self.client.login(username='hannah.acker', password='hannah.acker')

    def test_change_id_does_not_exist(self):
        response = self.client.get('/serverdb/recreate/-1')
        self.assertEqual(404, response.status_code)

    def test_recreate_succeeds(self):
        vm = Query().new_object('vm')
        vm['hostname'] = 'test-serverdb-recreate'
        vm['intern_ip'] = ip_address('10.0.0.1')
        vm.commit(user=User.objects.first())

        vm = Query({'hostname': 'test-serverdb-recreate'})
        object_id = vm.get()['object_id']
        vm.delete()
        vm.commit(user=User.objects.first())

        change_id = Change.objects.filter(
            object_id=object_id, change_type=Change.Type.DELETE).first().id
        response = self.client.get(
            f'/serverdb/recreate/{change_id}', follow=True)

        # recreate view should have created the object again and redirect us
        # to the history of it.
        self.assertEqual(200, response.status_code)
        self.assertEqual('serverdb/history.html', response.template_name)
        self.assertEqual(302, response.redirect_chain[0][1])

    def test_recreate_fails_if_hostname_exists(self):
        vm = Query().new_object('vm')
        vm['hostname'] = 'test-serverdb-recreate'
        vm['intern_ip'] = ip_address('10.0.0.1')
        vm.commit(user=User.objects.first())

        vm = Query({'hostname': 'test-serverdb-recreate'})
        object_id = vm.get()['object_id']
        vm.delete()
        vm.commit(user=User.objects.first())

        vm = Query().new_object('vm')
        vm['hostname'] = 'test-serverdb-recreate'
        vm['intern_ip'] = ip_address('10.0.0.2')
        vm.commit(user=User.objects.first())

        change_id = Change.objects.filter(
            object_id=object_id, change_type=Change.Type.DELETE).first().id
        response = self.client.get(
            f'/serverdb/recreate/{change_id}', follow=True)

        # Restore should have failed as there is already an object with that
        # hostname (again) and redirect us to changes view and display an
        # error.
        self.assertEqual(200, response.status_code)
        self.assertEqual('serverdb/changes.html', response.template_name)
        self.assertEqual(302, response.redirect_chain[0][1])


class HistoryViewTest(TransactionTestCase):
    fixtures = ['auth_user.json', 'test_dataset.json']

    def setUp(self) -> None:
        self.client.login(username='hannah.acker', password='hannah.acker')

        self.object_ids = []
        for i in (1, 2):
            vm = Query().new_object('vm')
            vm['hostname'] = f'test-serverdb-history-{i}'
            vm['intern_ip'] = ip_address(f'10.0.0.{i}')
            vm.commit(user=User.objects.first())
            self.object_ids.append(
                Query({'hostname': f'test-serverdb-history-{i}'}).get()[
                    'object_id'])

        vms = Query({'object_id': Any(*self.object_ids)}, ['intern_ip'])
        for i, vm in enumerate(vms, start=11):
            vm['intern_ip'] = ip_address(f'10.0.0.{i}')
        vms.commit(user=User.objects.first())

    def _url(self, *object_ids, **params):
        query = '&'.join(f'object_id={i}' for i in object_ids)
        for key, value in params.items():
            query += f'&{key}={value}'
        return f'/serverdb/history?{query}'

    def test_multiple_objects(self):
        response = self.client.get(self._url(*self.object_ids))

        self.assertEqual(200, response.status_code)
        self.assertEqual('2 objects', response.context['name'])
        changes = list(response.context['changes'])
        self.assertEqual(
            set(self.object_ids), {c.object_id for c in changes})
        self.assertEqual(
            {'test-serverdb-history-1', 'test-serverdb-history-2'},
            {c.hostname for c in changes})

    def test_single_object(self):
        response = self.client.get(self._url(self.object_ids[0]))

        self.assertEqual(200, response.status_code)
        self.assertEqual('test-serverdb-history-1', response.context['name'])
        self.assertEqual(
            {self.object_ids[0]},
            {c.object_id for c in response.context['changes']})

    def test_attribute_filter(self):
        response = self.client.get(
            self._url(*self.object_ids, attribute_filter='intern_ip'))

        changes = list(response.context['changes'])
        self.assertTrue(changes)
        self.assertTrue(all('intern_ip' in c.change_json for c in changes))
        self.assertEqual(
            set(self.object_ids), {c.object_id for c in changes})

    def test_missing_object_is_skipped(self):
        response = self.client.get(self._url(self.object_ids[0], 999999999))

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [self.object_ids[0]], response.context['object_ids'])
        self.assertIn(
            '999999999',
            ' '.join(str(m) for m in response.context['messages']))

    def test_only_missing_objects_redirects(self):
        response = self.client.get(self._url(999999999), follow=True)

        self.assertEqual('serverdb/changes.html', response.template_name)
        self.assertEqual(302, response.redirect_chain[0][1])

    def test_no_parameter(self):
        response = self.client.get('/serverdb/history')
        self.assertEqual(400, response.status_code)

    def test_changes_multiple_objects(self):
        object_ids = ','.join(str(i) for i in self.object_ids)
        response = self.client.get(
            f'/serverdb/changes?object_id={object_ids}')

        self.assertEqual(200, response.status_code)
        commit_ids = [c.id for c in response.context['commits']]
        # Two creates and one shared update commit, without duplicates
        self.assertEqual(3, len(commit_ids))
        self.assertEqual(len(commit_ids), len(set(commit_ids)))
