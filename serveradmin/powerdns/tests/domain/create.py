from serveradmin.powerdns.models import Domain, Record
from serveradmin.powerdns.tests.base import PowerDNSTests, create_test_object


class PowerDNSDomainCreateTests(PowerDNSTests):
    def test_domain_name(self) -> None:
        """Test PowerDNS domain has Serveradmin domain hostname as name

        :return:
        """

        name = create_test_object('domain').get()['hostname']
        self.assertTrue(
            Domain.objects.filter(name=name).exists(),
            f'No domain with name {name} found')

    def test_domain_id(self) -> None:
        """Test PowerDNS domain has Serveradmin object_id as id

        :return:
        """

        object_id = create_test_object('domain').get()['object_id']
        self.assertTrue(
            Domain.objects.filter(id=object_id).exists(),
            f'No domain with object_id {object_id} found')

    def test_other_servertype_creates_no_domain(self) -> None:
        """Test Serveradmin objects other than servertype domain create nothing

        :return:
        """

        object_id = create_test_object('lb_pool').get()['object_id']
        self.assertFalse(
            Domain.objects.filter(id=object_id).exists(),
            'Extra domain found for servertype lb_pool')

    def test_domain_type_default(self) -> None:
        """Test default PowerDNS domain type is NATIVE

        :return:
        """

        object_id = create_test_object('domain').get()['object_id']
        self.assertEqual(
            Domain.objects.get(id=object_id).type, 'NATIVE',
            'Default domain type must be NATIVE')

    def test_domain_type(self) -> None:
        """Test custom PowerDNS domain type equals Serveradmin object one

        :return:
        """

        object_id = create_test_object(
            'domain', type='MASTER').get()['object_id']
        self.assertEqual(
            Domain.objects.get(id=object_id).type, 'MASTER',
            'Domain type must be MASTER')

    def test_domain_soa_record(self) -> None:
        """Test PowerDNS SOA record exists for a new Serveradmin domain

        :return:
        """

        object_id = create_test_object(
            'domain', soa=self.soa).get()['object_id']
        record = Record.objects.filter(
            domain_id=object_id, type='SOA', content=self.soa)
        self.assertTrue(record.exists(), 'Missing SOA record')

    def test_domain_ns_records(self) -> None:
        """Test PowerDNS NS records exist for a new Serveradmin domain

        :return:
        """

        object_id = create_test_object(
            'domain', ns=self.ns).get()['object_id']
        records = Record.objects.filter(
            domain_id=object_id, type='NS', content__in=self.ns)
        self.assertEqual(records.count(), 2, 'Expected 2 NS records')
