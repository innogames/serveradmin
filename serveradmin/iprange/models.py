from copy import copy

from django.db import models, connection

from adminapi.utils import Network
from serveradmin.common import dbfields
from serveradmin.dataset.base import lookups
from serveradmin.dataset.exceptions import DatasetError
from serveradmin.dataset.querybuilder import QueryBuilder
from serveradmin.dataset import filters

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
    internal_gateway = dbfields.IPv4Field(null=True)
    belongs_to = models.ForeignKey('IPRange', null=True, blank=True,
            related_name='subnet_of')

    def get_free(self, increase_pointer=True):
        c = connection.cursor()
        c.execute("SELECT GET_LOCK('serverobject_commit', 10)")
        try:
            next_free = copy(self.next_free)
            if next_free >= self.max:
                next_free = self.min + 1
            elif next_free <= self.min:
                next_free = self.min + 1
            for second_loop in (False, True):
                while next_free <= self.max - 1:
                    if _is_taken(next_free.as_int()):
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
                next_free = self.min + 1
                if second_loop:
                    raise DatasetError('No more free addresses, sorry')
        finally:
            c.execute("SELECT RELEASE_LOCK('serverobject_commit')")

    def get_network(self):
        return Network(self.min, self.max)

    def get_taken_set(self):
        # Query taken IPs
        f_between = filters.Between(self.min, self.max)
        builder = QueryBuilder()
        builder.add_attribute('all_ips')
        builder.add_filter('all_ips', f_between)
        fields = lookups.attr_names['all_ips'].special.attrs
        builder.add_select(*fields)
        
        # Collect taken IPs in set
        taken_ips = set()
        c = connection.cursor()
        c.execute(builder.build_sql())
        for ip_tuple in c.fetchall():
            for ip in ip_tuple:
                if ip is not None and self.min <= ip <= self.max:
                    taken_ips.add(int(ip))

        return taken_ips

    def get_free_set(self):
        free_ips = set()
        taken_ips = self.get_taken_set()
        for ip_int in xrange(self.min.as_int() + 1, self.max.as_int()):
            if ip_int not in taken_ips:
                free_ips.add(ip_int)
        
        return free_ips

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

def _is_taken(ip):
    attrib_id = lookups.attr_names['additional_ips'].pk
    query = ('SELECT (SELECT COUNT(*) FROM admin_server '
             '        WHERE intern_ip = %s) + '
             '       (SELECT COUNT(*) FROM attrib_values '
             '        WHERE value = %s AND attrib_id = {0})').format(attrib_id)
    c = connection.cursor()
    c.execute(query, (ip, ip))
    result = c.fetchone()[0]
    c.close()
    return result != 0


def get_gateways(ip):

    ipranges = IPRange.objects.filter(min__lte=ip, max__gte=ip)
    ipranges = [iprange for iprange in ipranges if iprange is not None]

    if not ipranges:
        raise ValueError('IP is not in known IP ranges')
    
    def get_range_size(iprange_obj):
        return iprange_obj.max.as_int() - iprange_obj.min.as_int()

    iprange_obj = min(ipranges, key=get_range_size)

    def get_netmask(iprange_obj):
        if iprange_obj.ip_type == 'ip':
            return '255.255.0.0'
        else:
            #netmask calculation via: http://stackoverflow.com/questions/8872636/how-to-calculate-netmask-from-2-ip-adresses-in-python
            m = 0xFFFFFFFF ^ iprange_obj.min.as_int() ^ iprange_obj.max.as_int()
            netmask = [(m & (0xFF << (8*n))) >> 8*n for n in (3, 2, 1, 0)]
            return '.'.join([ str(i) for i in netmask])

    def get_gw(iprange_obj, gw_attr):
        if getattr(iprange_obj, gw_attr, None) is not None:
            return [getattr(iprange_obj, gw_attr), get_netmask(iprange_obj)]
        if iprange_obj.belongs_to_id is None:
            return None

        iprange_obj = IPRange.objects.get(range_id=iprange_obj.belongs_to_id)
        return get_gw(iprange_obj, gw_attr)

    return {
        'default_gateway': get_gw(iprange_obj, 'gateway'),
        'internal_gateway': get_gw(iprange_obj, 'internal_gateway')
    }


def _get_network_settings(ip):
    ipranges = IPRange.objects.filter(min__lte=ip, max__gte=ip)
    ipranges = [iprange for iprange in ipranges if iprange is not None]

    if not ipranges:
        raise ValueError('IP is not in known IP ranges')

    def get_range_size(iprange_obj):
        return iprange_obj.max.as_int() - iprange_obj.min.as_int()

    # This is the smallest matching IP range.
    # For most of things we will traverse to his parents.
    iprange_obj = min(ipranges, key=get_range_size)

    def calculate_netmask(iprange_obj):
            #netmask calculation via: http://stackoverflow.com/questions/8872636/how-to-calculate-netmask-from-2-ip-adresses-in-python
            m = 0xFFFFFFFF ^ iprange_obj.min.as_int() ^ iprange_obj.max.as_int()
            netmask = [(m & (0xFF << (8*n))) >> 8*n for n in (3, 2, 1, 0)]
            return '.'.join([ str(i) for i in netmask])

    # Traverse to parent ip_range if given parameter is not specified.
    def nonempty_parent(iprange_obj, param):
        if getattr(iprange_obj, param, None) is not None:
            return getattr(iprange_obj, param)
        if iprange_obj.belongs_to_id is None:
            return None
        iprange_obj = IPRange.objects.get(range_id=iprange_obj.belongs_to_id)
        return nonempty_parent(iprange_obj, param)

    # Traverse to parent ip_range if there is any.
    def highest_parent(iprange_obj):
        if iprange_obj.belongs_to_id:
            iprange_obj = IPRange.objects.get(range_id=iprange_obj.belongs_to_id)
            return highest_parent(iprange_obj)
        else:
            return iprange_obj

    default_gateway = nonempty_parent(iprange_obj, 'gateway')
    internal_gateway = nonempty_parent(iprange_obj, 'internal_gateway')

    return {
        'default_gateway':  str(default_gateway) if default_gateway else None,
        'internal_gateway': str(internal_gateway) if internal_gateway else None,
        'broadcast': str(iprange_obj.max),
        'netmask': calculate_netmask(highest_parent(iprange_obj))
    }

def _get_iprange_settings(name):
    ipranges = IPRange.objects.filter(range_id=name)
    if not len(ipranges)==1:
        raise ValueError('IP Range not found by name')
    iprange_obj = ipranges[0]
    print iprange_obj.gateway

    def calculate_netmask(iprange_obj):
            #netmask calculation via: http://stackoverflow.com/questions/8872636/how-to-calculate-netmask-from-2-ip-adresses-in-python
            m = 0xFFFFFFFF ^ iprange_obj.min.as_int() ^ iprange_obj.max.as_int()
            netmask = [(m & (0xFF << (8*n))) >> 8*n for n in (3, 2, 1, 0)]
            return '.'.join([ str(i) for i in netmask])

    return {
        'default_gateway':  str(iprange_obj.gateway) if iprange_obj.gateway else None,
        'internal_gateway': str(iprange_obj.internal_gateway) if iprange_obj.internal_gateway else None,
        'broadcast': str(iprange_obj.max),
        'netmask': calculate_netmask(iprange_obj)
    }

