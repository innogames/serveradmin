from serveradmin.powerdns.models import Domain, Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_test_object


class PowerDNSDomainDeleteTests(PowerDNSTests):
    def test_delete(self):
        """Test deleting a domain object deletes the PowerDNS domain

        :return:
        """

        domain_query = create_test_object('domain')

        domain = Domain.objects.filter(id=domain_query.get()['object_id'])
        self.assertTrue(domain.exists(), 'Missing domain')

        domain_query.delete()
        domain_query.commit(user=self.user)

        self.assertFalse(domain.exists(), 'Domain not deleted')

    def test_records_are_deleted(self):
        """Test deleting a domain deletes all PowerDNS records

        :return:
        """

        domain_query = create_test_object('domain')
        domain_id = domain_query.get()['object_id']

        # There should be at least SOA and NS records
        records = Record.objects.filter(domain_id=domain_id)
        self.assertGreater(records.count(), 1, 'No records found for domain')

        domain_query.delete()
        domain_query.commit(user=self.user)

        self.assertFalse(records.exists(), 'Records not deleted')
