from django.core.exceptions import PermissionDenied
from django.test import TransactionTestCase

from serveradmin.apps.models import Application
from serveradmin.dataset import Query


class TestAttributeRelatedViaPermissions(TransactionTestCase):
    fixtures = ['auth_user.json', 'apps.json', 'serverdb.json', 'access_control.json']

    # See https://github.com/innogames/serveradmin/pull/351
    def test_can_commit_related_via_attribute(self):
        hv_1 = Query().new_object("hv")
        hv_1["hostname"] = "hv-1"
        hv_1["nic"] = "nic-1"
        hv_1.commit(app=Application.objects.filter(superuser=True).first())

        hv_2 = Query().new_object("hv")
        hv_2["hostname"] = "hv-2"
        hv_2["nic"] = "nic-2"
        hv_2.commit(app=Application.objects.filter(superuser=True).first())

        vm = Query().new_object("vm")
        vm["hostname"] = "vm-1"
        vm["hv"] = "hv-1"
        vm.commit(app=Application.objects.filter(superuser=True).first())

        vm = Query({"hostname": "vm-1"}, ["hostname", "hv"])
        vm.update(hv="hv-2")
        self.assertIsInstance(vm.commit(app=Application.objects.get(name="test")), int)

    # See https://github.com/innogames/serveradmin/pull/351
    def test_cannot_commit_related_via_attribute_target(self):
        hv_1 = Query().new_object("hv")
        hv_1["hostname"] = "hv-1"
        hv_1["nic"] = "nic-1"
        hv_1.commit(app=Application.objects.filter(superuser=True).first())

        hv_2 = Query().new_object("hv")
        hv_2["hostname"] = "hv-2"
        hv_2["nic"] = "nic-2"
        hv_2.commit(app=Application.objects.filter(superuser=True).first())

        vm = Query().new_object("vm")
        vm["hostname"] = "vm-1"
        vm["hv"] = "hv-1"
        vm.commit(app=Application.objects.filter(superuser=True).first())

        vm = Query({"hostname": "hv-1"}, ["hostname", "nic"])
        vm.update(nic="hv-2")
        self.assertRaises(PermissionDenied, vm.commit, app=Application.objects.get(name="test"))
