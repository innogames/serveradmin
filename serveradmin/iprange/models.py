from django.db import models, connection

from adminapi.utils import IP
from adminapi.dataset.base import DatasetError
from serveradmin.dataset import query
from serveradmin.api.decorators import api_function
from serveradmin.api import ApiError

IP_CHOICES = (
    ('ip', 'Internal IP'),
    ('public_ip', 'Public IP'),
)

class IPRange(models.Model):
    range_id = models.CharField(max_length=20, primary_key=True)
    segment = models.CharField(max_length=30, db_column='segment_id')
    ip_type = models.CharField(max_length=10, choices=IP_CHOICES)
    min = models.IntegerField()
    max = models.IntegerField()
    next_free = models.IntegerField()

    def get_free(self, increase_pointer=True):
        c = connection.cursor()
        c.execute("SELECT GET_LOCK('serverobject_commit', 10)")
        try:
            next_free = self.next_free
            for second_loop in (False, True):
                while next_free <= self.max:
                    if query(all_ips=next_free).restrict('hostname'):
                        next_free += 1
                    else:
                        if increase_pointer:
                            self.next_free = next_free + 1
                            self.save()
                        return IP(next_free)
                next_free = self.min
                if second_loop:
                    raise DatasetError('No more free addresses, sorry')
        finally:
            c.execute("SELECT RELEASE_LOCK('serverobject_commit')")

    class Meta:
        db_table = 'ip_range'
    
    def __unicode__(self):
        return self.range_id

@api_function(group='ip')
def get_free(range_id, reserve_ip=True):
    """Return a free IP address.

    If ``reserve_ip`` is set to ``True`` it will return a different IP
    on the next call unless all other IPs are used. This can be used
    to reserve the IP so other scripts won't get the returned IP if
    you haven't added a server with this IP yet.
    """
    try:
        r = IPRange.objects.get(range_id=range_id)
        return r.get_free(increase_pointer=reserve_ip).as_ip()
    except IPRange.DoesNotExist:
        raise ApiError('No such IP range')
    except DatasetError, e:
        raise ApiError(e.message)
