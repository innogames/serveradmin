from django.contrib.auth.models import User
from django.test import TransactionTestCase
from netaddr import IPAddress

from serveradmin.dataset import Query
from serveradmin.serverdb.models import Change


class RestoreViewTest(TransactionTestCase):
    fixtures = ['auth_user.json', 'test_dataset.json']

    def setUp(self) -> None:
        self.client.login(username='hannah.acker', password='hannah.acker')

    def test_change_id_does_not_exist(self):
        response = self.client.get('/serverdb/restore/-1')
        self.assertEqual(404, response.status_code)

    def test_restore_succeeds(self):
        vm = Query().new_object('vm')
        vm['hostname'] = 'test-serverdb-restore'
        vm['intern_ip'] = IPAddress('10.0.0.1')
        vm.commit(user=User.objects.first())

        vm = Query({'hostname': 'test-serverdb-restore'})
        object_id = vm.get()['object_id']
        vm.delete()
        vm.commit(user=User.objects.first())

        change_id = Change.objects.filter(
            object_id=object_id, change_type=Change.Type.DELETE).first().id
        response = self.client.get(
            f'/serverdb/restore/{change_id}', follow=True)

        # restore view should have created the object again and redirect us
        # to the history of it.
        self.assertEqual(200, response.status_code)
        self.assertEqual('serverdb/history.html', response.template_name)
        self.assertEqual(302, response.redirect_chain[0][1])

    def test_restore_fails_if_hostname_exists(self):
        vm = Query().new_object('vm')
        vm['hostname'] = 'test-serverdb-restore'
        vm['intern_ip'] = IPAddress('10.0.0.1')
        vm.commit(user=User.objects.first())

        vm = Query({'hostname': 'test-serverdb-restore'})
        object_id = vm.get()['object_id']
        vm.delete()
        vm.commit(user=User.objects.first())

        vm = Query().new_object('vm')
        vm['hostname'] = 'test-serverdb-restore'
        vm['intern_ip'] = IPAddress('10.0.0.2')
        vm.commit(user=User.objects.first())

        change_id = Change.objects.filter(
            object_id=object_id, change_type=Change.Type.DELETE).first().id
        response = self.client.get(
            f'/serverdb/restore/{change_id}', follow=True)

        # Restore should have failed as there is already an object with that
        # hostname (again) and redirect us to changes view and display an
        # error.
        self.assertEqual(200, response.status_code)
        self.assertEqual('serverdb/changes.html', response.template_name)
        self.assertEqual(302, response.redirect_chain[0][1])
