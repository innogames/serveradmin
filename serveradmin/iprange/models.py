from copy import copy

from django.db import models, connection

from adminapi.utils import Network
from serveradmin.common import dbfields
from serveradmin.dataset import query, DatasetError

IP_CHOICES = (
    ('ip', 'Private'),
    ('public_ip', 'Public'),
)

class IPRange(models.Model):
    range_id = models.CharField(max_length=20, primary_key=True)
    segment = models.CharField(max_length=30, db_column='segment_id')
    ip_type = models.CharField(max_length=10, choices=IP_CHOICES)
    min = dbfields.IPv4Field()
    max = dbfields.IPv4Field()
    next_free = dbfields.IPv4Field()
    gateway = dbfields.IPv4Field(null=True)
    belongs_to = models.ForeignKey('IPRange', null=True, blank=True,
            related_name='subnet_of')

    def get_free(self, increase_pointer=True):
        c = connection.cursor()
        c.execute("SELECT GET_LOCK('serverobject_commit', 10)")
        try:
            next_free = min(max(self.next_free, self.min + 1), self.max - 1)
            for second_loop in (False, True):
                while next_free <= self.max - 1:
                    if query(all_ips=next_free).restrict('hostname'):
                        next_free += 1
                    elif (next_free.as_int() & 0xff) in (0x00, 0xff):
                        next_free += 1
                    else:
                        if increase_pointer:
                            IPRange.objects.filter(next_free=next_free).update(
                                    next_free=next_free + 1)
                            self.next_free = next_free + 1
                            self.save()
                        return next_free
                next_free = copy(self.min + 1)
                if second_loop:
                    raise DatasetError('No more free addresses, sorry')
        finally:
            c.execute("SELECT RELEASE_LOCK('serverobject_commit')")

    def get_network(self):
        return Network(self.min, self.max)

    @property
    def cidr(self):
        try:
            return self.get_network().as_cidr()
        except TypeError:
            return None

    class Meta:
        db_table = 'ip_range'
    
    def __unicode__(self):
        return self.range_id
