from ipaddress import ip_address

from django.test import TestCase

from serveradmin.dataset import query, filters, create


class TestQuery(TestCase):
    fixtures = ['test_dataset.json']

    def test_query_hostname(self):
        s = query(hostname=u'test0').get()
        self.assertEqual(s[u'hostname'], u'test0')

    def test_query_os(self):
        s = query(os=u'wheezy').get()
        self.assertEquals(s[u'hostname'], 'test0')

    def test_query_iterate(self):
        hostnames = set()
        for s in query():
            hostnames.add(s[u'hostname'])

        self.assertIn(u'test0', hostnames)
        self.assertIn(u'test1', hostnames)
        self.assertIn(u'test2', hostnames)
        self.assertIn(u'test3', hostnames)

    def test_filter_regexp(self):
        hostnames = set()
        for s in query(hostname=filters.Regexp(ur'^test[02]$')):
            hostnames.add(s[u'hostname'])

        self.assertIn(u'test0', hostnames)
        self.assertNotIn(u'test1', hostnames)
        self.assertIn(u'test2', hostnames)

    def test_filter_regexp_servertype(self):
        s = query(servertype=filters.Regexp(ur'^test[870]')).get()
        self.assertEquals(s[u'hostname'], u'test0')

    def test_filter_comparison(self):
        hostnames = set()
        for s in query(game_world=filters.Comparison('<', 2)):
            hostnames.add(s['hostname'])

        self.assertNotIn(u'test0', hostnames)
        self.assertIn(u'test1', hostnames)
        self.assertNotIn(u'test2', hostnames)
        self.assertNotIn(u'test3', hostnames)

    def test_filter_any(self):
        hostnames = set()
        for s in query(hostname=filters.Any(u'test1', u'test3')):
            hostnames.add(s[u'hostname'])

        self.assertNotIn(u'test0', hostnames)
        self.assertIn(u'test1', hostnames)
        self.assertNotIn(u'test2', hostnames)
        self.assertIn(u'test3', hostnames)

    def test_and(self):
        pass

    def test_or(self):
        q = query(game_world=filters.Or(
            filters.Comparison(u'<', 2),
            filters.Comparison(u'>', 7),
        ))
        hostnames = set()
        for s in q:
            hostnames.add(s[u'hostname'])

        self.assertNotIn(u'test0', hostnames)
        self.assertIn(u'test1', hostnames)
        self.assertNotIn(u'test2', hostnames)
        self.assertIn(u'test3', hostnames)

    def test_not(self):
        s = query(os=filters.Not('squeeze')).get()
        self.assertEquals(s[u'hostname'], u'test0')

    def test_not_filter(self):
        s = query(os=filters.Not(filters.Any('squeeze', 'lenny'))).get()
        self.assertEquals(s[u'hostname'], u'test0')

    def test_between(self):
        hostnames = set()
        for s in query(game_world=filters.Between(2, 10)):
            hostnames.add(s[u'hostname'])

        self.assertNotIn(u'test0', hostnames)
        self.assertNotIn(u'test1', hostnames)
        self.assertIn(u'test2', hostnames)
        self.assertIn(u'test3', hostnames)

    def test_startswith(self):
        s = query(os=filters.Startswith('whee')).get()
        self.assertEquals(s[u'hostname'], u'test0')

    def test_startswith_servertype(self):
        q = query(servertype=filters.Startswith('tes'))
        self.assertEquals(len(q), 4)

    def test_optional(self):
        hostnames = set()
        for s in query(game_world=filters.Optional(1)):
            hostnames.add(s[u'hostname'])

        self.assertIn(u'test0', hostnames)
        self.assertIn(u'test1', hostnames)
        self.assertNotIn(u'test2', hostnames)
        self.assertNotIn(u'test3', hostnames)


class TestCommit(TestCase):
    fixtures = ['test_dataset.json']

    def test_commit_queryset(self):
        q = query(hostname=u'test1')
        s = q.get()
        s[u'os'] = u'wheezy'
        s[u'segment'] = u'seg1'
        s[u'intern_ip'] = u'10.16.2.1'
        q.commit()

        s = query(hostname=u'test1').get()
        self.assertEquals(s[u'os'], u'wheezy')
        self.assertEquals(s[u'segment'], u'seg1')
        self.assertEquals(s[u'intern_ip'], ip_address('10.16.2.1'))

    def test_commit_regexp_violation(self):
        pass

    def test_commit_attr_not_exist(self):
        pass

    def test_commit_servertype(self):
        pass

    def test_commit_hostname(self):
        pass

    def test_commit_intern_ip(self):
        pass

    def test_commit_newer_data(self):
        pass


class TestCreate(TestCase):
    def test_create(self):
        s = {
            u'hostname': u'test4',
            u'intern_ip': u'127.0.0.1',
            u'servertype': u'test0',
            u'segment': u'seg0.r0',
            u'os': u'squeeze',
            u'database': [u'pgsql']
        }
        s_res = create(s, fill_defaults=True, fill_defaults_all=True)
        self.assertEqual(s_res[u'hostname'], u'test4')
