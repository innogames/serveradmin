from random import random

from freezegun import freeze_time

from serveradmin.powerdns.models import Domain, Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_test_object


class PowerDNSDomainUpdateTests(PowerDNSTests):
    def test_domain_name(self) -> None:
        """Test PowerDNS domain name updates when Serveradmin hostname changes

        :return:
        """

        domain_query = create_test_object('domain')
        domain_id = domain_query.get()['object_id']

        new_name = str(random())
        domain_query.update(hostname=new_name)
        domain_query.commit(user=self.user)

        domain = Domain.objects.filter(id=domain_id, name=new_name)
        self.assertTrue(domain.exists(), f'Domain name is {new_name}')

    def test_record_names(self) -> None:
        """Test PowerDNS domain name update updates record names

        :return:
        """

        domain_query = create_test_object('domain')
        domain_id = domain_query.get()['object_id']

        new_name = str(random())
        domain_query.update(hostname=new_name)
        domain_query.commit(user=self.user)

        records = Record.objects.filter(domain_id=domain_id, name=new_name)
        # The template has 1x SOA, 1x NS record
        self.assertEqual(records.count(), 2, 'Not all record names updated')

    def test_record_names_updates_change_date(self) -> None:
        """Test PowerDNS domain name update updates records change_date

        :return:
        """

        domain_query = create_test_object('domain')

        domain_id = domain_query.get()['object_id']
        change_dates = Record.objects.filter(
            domain_id=domain_id).values_list('change_date', flat=True)

        new_name = str(random())
        domain_query.update(hostname=new_name)
        with freeze_time('1970-01-01 12:00'):
            domain_query.commit(user=self.user)

        new_change_dates = Record.objects.filter(
            domain_id=domain_id).values_list('change_date', flat=True)

        self.assertNotEqual(
            change_dates, new_change_dates, 'Not all change dates updated')

    def test_change_soa_value(self) -> None:
        """Test changing the soa attribute updates the PowerDNS SOA record

        :return:
        """

        domain_query = create_test_object('domain')
        domain_id = domain_query.get()['object_id']

        new_soa = self.soa + 'abc'
        domain_query.update(soa=new_soa)
        domain_query.commit(user=self.user)

        record = Record.objects.filter(
            domain_id=domain_id, type='SOA', content=new_soa)
        self.assertTrue(
            record.exists(),
            f'SOA record content should be {new_soa}')

    def test_change_soa_value_updates_change_date(self) -> None:
        """Test changing the soa value updates the PowerDNS change date

        :return:
        """

        domain_query = create_test_object('domain')
        domain_id = domain_query.get()['object_id']

        # The changed_date at creation
        change_date = Record.objects.get(
            domain_id=domain_id, type='SOA').change_date

        domain_query.update(soa=self.soa + 'abc')
        with freeze_time('1970-01-01 12:00'):
            domain_query.commit(user=self.user)

        new_change_date = Record.objects.get(
            domain_id=domain_id, type='SOA').change_date
        self.assertNotEqual(
            change_date, new_change_date, 'change_date is the same')

    def test_add_ns_value(self) -> None:
        """Test adding a ns attribute value creates a new PowerDNS NS record

        :return:
        """

        domain_query = create_test_object('domain')
        domain_id = domain_query.get()['object_id']

        to_add = 'pdns3.example.com'
        domain_query.get()['ns'].add(to_add)
        domain_query.commit(user=self.user)

        record = Record.objects.filter(
            domain_id=domain_id, type='NS', content=to_add)
        self.assertTrue(
            record.exists(),
            f'Missing NS record with content {to_add}')

    def test_remove_ns_value(self) -> None:
        """Test removing a ns attribute value delete the PowerDNS NS record

        :return:
        """

        domain_query = create_test_object('domain')
        domain_id = domain_query.get()['object_id']

        to_delete = 'pdns1.example.com'
        record = Record.objects.filter(
            domain_id=domain_id, type='NS', content=to_delete)

        self.assertTrue(record.exists(), 'Record exists before')

        domain_query.get()['ns'].remove(to_delete)
        domain_query.commit(user=self.user)

        self.assertFalse(
            record.exists(), f'Record {to_delete} has been deleted')
