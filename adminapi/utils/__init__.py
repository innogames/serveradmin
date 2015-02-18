from __future__ import print_function
import sys
from socket import inet_pton, inet_ntop, AF_INET6, error
from binascii import hexlify, unhexlify
from itertools import izip
import struct
import warnings

def log2(x):
    i = -1
    while x:
        x >>= 1
        i += 1
    return i

def print_table(input_table_rows, max_col_len=40, file=sys.stdout):
    if not input_table_rows:
        return
    
    # Format objects for table display
    table_rows = []
    for row in input_table_rows:
        cols = []
        for col in row:
            formatted_obj = format_obj(col)
            if len(formatted_obj) > max_col_len - 4:
                cols.append(formatted_obj[0:max_col_len] + u' ...')
            else:
                cols.append(formatted_obj)
        table_rows.append(cols)

    # Get maximal length for all columns
    column_lens = [0] * len(table_rows[0])
    for row in table_rows:
        for col_no, col in enumerate(row):
            column_lens[col_no] = max(column_lens[col_no], len(col))

    sep = '+-{0}-+'.format('-+-'.join('-' * col_len for col_len in column_lens))
    print(sep, file=file)
    for row_no, row in enumerate(table_rows):
        if row_no == 1:
            print(sep, file=file)
        table_line = '| {0} |'.format(' | '.join(col.ljust(col_len)
            for col, col_len in izip(row, column_lens)))
        print(table_line, file=file)
    print(sep, file=file)

def format_obj(obj):
    if isinstance(obj, basestring):
        return obj
    elif hasattr(obj, '__iter__'):
        return ', '.join(sorted(unicode(x) for x in obj))
    else:
        return unicode(obj)

def print_heading(heading, char='-', file=sys.stdout):
    print('{0}\n{1}\n'.format(heading, char * len(heading)),
            file=file)

def _base256_encode(n):
    if n < 0:
        raise ValueError("Invalid long for IPv6")
    upper_bits = n >> 64
    lower_bits = n & 0xffffffffffffffff
    return struct.pack('>QQ', upper_bits, lower_bits)

class IP(object):
    __slots__ = ('ip', )
    
    def __init__(self, ip):
        if isinstance(ip, basestring):
            ip_int = 0
            for seg in ip.split('.'):
                ip_int = ip_int << 8
                ip_int |= int(seg)
            self.ip = ip_int
        else:
            self.ip = ip

    def __str__(self):
        return self.as_ip()

    def __repr__(self):
        return 'IP({0!r})'.format(self.as_ip())

    def __eq__(self, other):
        if isinstance(other, IP):
            return self.ip == other.ip
        else:
            try:
                other = IP(other)
                return self.ip == other.ip
            except ValueError:
                return False

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if isinstance(other, IP):
            return self.ip < other.ip
        else:
            try:
                other = IP(other)
                return self.ip < other.ip
            except ValueError:
                return False

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not (self < other or self == other)
    
    def __ge__(self, other):
        return not self < other
    
    def __add__(self, other):
        return IP(self.ip + other)

    def __sub__(self, other):
        return IP(self.ip - other)

    def __iadd__(self, other):
        self.ip += other
        return self
    
    def __isub__(self, other):
        self.ip -= other
        return self

    def __getstate__(self):
        return (self.ip, )

    def __setstate__(self, state):
        self.ip = state[0]

    def __hash__(self):
        return hash(self.ip)

    def as_ip(self):
        ip = [0] * 4
        ip_int = self.ip
        for i in xrange(4):
            ip[i] = str(ip_int & 0xff)
            ip_int = ip_int >> 8
        
        return '.'.join(reversed(ip))

    __str__ = as_ip

    def as_int(self):
        return self.ip

    def is_private(self):
        return any(net.min_ip <= self.ip <= net.max_ip for net in PRIVATE_IP_BLOCKS)

    def is_internal(self):
        warnings.warn('is_internal() is deprecated. Use is_private() instead',
                DeprecationWarning)
        return self.is_private()

    def is_public(self):
        return not self.is_internal()

class IPv6(object):
    __slots__ = ('ip', )

    def __init__(self, ipv6):
        try:
            self.ip = inet_pton(AF_INET6, ipv6)
        except (error, TypeError) as e:
            raise ValueError(e)

    def __add__(self, other):
        return IPv6.from_long(self.as_long() + other)

    def __eq__(self, other):
        if isinstance(other, IPv6):
            return self.ip == other.ip
        else:
            try:
                other = IPv6(other)
                return self.ip == other.ip
            except ValueError:
                return False

    def __hash__(self):
        return hash(self.ip)

    def __iadd__(self, other):
        return IPv6.from_long(self.as_long() + other)

    def __isub__(self, other):
        return IPv6.from_long(self.as_long() - other)

    def __lt__(self, other):
        if isinstance(other, IPv6):
            return self.ip < other.ip
        else:
            try:
                other = IPv6(other)
                return self.ip < other.ip
            except ValueError:
                return False

    def __le__(self, other):
        return self < other or self == other

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return 'IPv6({0!r})'.format(self.as_ip())

    def __str__(self):
        return self.as_ip()

    def __sub__(self, other):
        return IPv6.from_long(self.as_long() - other)

    def __getstate__(self):
        return (self.ip, )

    def __setstate__(self, state):
        self.ip = state[0]

    @classmethod
    def from_hex(cls, hexcode):
        byte_string = unhexlify(hexcode)
        ipv6 = inet_ntop(AF_INET6, byte_string)
        return cls(ipv6)

    @classmethod
    def from_bytes(cls, byte_string):
        ipv6 = inet_ntop(AF_INET6, byte_string)
        return cls(ipv6)

    @classmethod
    def from_long(cls, long_num):
        byte_string = _base256_encode(long_num)
        return cls.from_bytes(byte_string)

    def as_ip(self):
        return inet_ntop(AF_INET6, self.ip)

    def as_bytes(self):
        return self.ip

    def as_hex(self):
        return hexlify(self.ip)

    def as_long(self):
        return int(self.as_hex(), 16)

    def is_private(self):
        return not self.is_public()

    def is_public(self):
        # Check if IP starts with 001 (in binary)
        return (ord(self.ip[0]) ^ 0b00100000) & 0b11100000 == 0

    __str__ = as_ip

class Network(object):
    def __init__(self, min_ip, max_ip=None):
        if max_ip is None:
            if isinstance(min_ip, basestring):
                cidr_ip, size = min_ip.split('/')
                cidr_ip_int = IP(cidr_ip).as_int()
                mask = -1 << (32 - int(size))
                self.min_ip = IP(cidr_ip_int & mask)
                self.max_ip = IP(self.min_ip.as_int() | ~mask)
            elif isinstance(list, tuple):
                self.min_ip = IP(min_ip[0])
                self.max_ip = IP(max_ip[0])
            else:
                raise ValueError("Can't convert {0} to network".format(min_ip))
        else:
            self.min_ip = IP(min_ip) if not isinstance(min_ip, IP) else min_ip
            self.max_ip = IP(max_ip) if not isinstance(max_ip, IP) else max_ip

        if self.max_ip < self.min_ip:
            raise ValueError('max_ip must be greater or equal min_ip')

    def __hash__(self):
        return hash(self.min_ip) ^ hash(self.max_ip)

    def __eq__(self, other):
        if isinstance(other, Network):
            return self.min_ip == other.min_ip and self.max_ip == other.max_ip
        return False

    def __ne__(self, other):
        return not (self == other)

    def as_cidr(self):
        return u'{0}/{1}'.format(self.min_ip.as_ip(), self.prefix)

    @property
    def netmask(self):
        #netmask calculation via: http://stackoverflow.com/questions/8872636/how-to-calculate-netmask-from-2-ip-adresses-in-python
        m = 0xFFFFFFFF ^ self.min_ip.as_int() ^ self.max_ip.as_int()
        netmask = [(m & (0xFF << (8*n))) >> 8*n for n in (3, 2, 1, 0)]
        return '.'.join([ str(i) for i in netmask])

    @property
    def prefix(self):
        num_ips = self.max_ip.as_int() - self.min_ip.as_int() + 1
        power_of_two = (num_ips & (num_ips - 1)) == 0
        if not power_of_two:
            raise TypeError("Network can't be converted to cidr")
        size = 32 - log2(num_ips)
        return size

    def __repr__(self):
        try:
            return u'Network({0!r})'.format(self.as_cidr())
        except TypeError:
            return u'Network({0!r}, {1!r})'.format(self.min_ip, self.max_ip)

    def inside(self, ip):
        return self.min_ip <= ip <= self.max_ip

class Network6(object):
    def __init__(self, min_ip, max_ip=None):
        if max_ip is None:
            if isinstance(min_ip, basestring):
                cidr_ip, size = min_ip.split('/')
                cidr_ip_int = IPv6(cidr_ip).as_hex()
                mask = -1 << (128 - int(size))
                tmp_min = IPv6.from_long(int(cidr_ip_int, 16) & mask)
                self.min_ip = tmp_min
                tmp_max = IPv6.from_long(int(self.min_ip.as_hex(), 16) | ~mask)
                self.max_ip = tmp_max
            elif isinstance(list, tuple):
                self.min_ip = IPv6(min_ip[0])
                self.max_ip = IPv6(max_ip[0])
            else:
                raise ValueError("Can't convert {0} to IPv6 Network".format(min_ip))
        else:
            self.min_ip = IPv6(min_ip) if not isinstance(min_ip, IPv6) else min_ip
            self.max_ip = IPv6(max_ip) if not isinstance(max_ip, IPv6) else max_ip

        if self.max_ip.as_long() < self.min_ip.as_long():
            raise ValueError('max_ip ({0})must be greater or equal min_ip ({0})'.format(self.min_ip, self.max_ip))

    def __hash__(self):
        return hash(self.min_ip) ^ hash(self.max_ip)

    def __eq__(self, other):
        if isinstance(other, Network6):
            return self.min_ip == other.min_ip and self.max_ip == other.max_ip
        return False

    def __ne__(self, other):
        return not (self == other)

    def as_cidr(self):
        return u'{0}/{1}'.format(self.min_ip.as_ip(), self.prefix)

    @property
    def prefix(self):
        num_ips = self.max_ip.as_long() - self.min_ip.as_long() + 1
        power_of_two = (num_ips & (num_ips - 1)) == 0
        if not power_of_two:
            raise TypeError("Network can't be converted to IPv6 cidr")
        size = 128 - log2(num_ips)
        return size

    def __repr__(self):
        try:
            return u'Network6({0!r})'.format(self.as_cidr())
        except TypeError:
            return u'Network6({0!r}, {1!r})'.format(self.min_ip, self.max_ip)

    def inside(self, ip):
        if isinstance(ip, IPv6):
            ip = ip
        elif isinstance(ip, long) or isinstance(ip, int):
            ip = IPv6.from_long(ip)
        elif isinstance(ip, basestring):
            ip = IPv6(ip)
        else:
            raise ValueError('Can not convert given parameter type to a IPv6 address')
        return self.min_ip.as_long() <= ip.as_long() <= self.max_ip.as_long()

# http://en.wikipedia.org/wiki/Private_network
PRIVATE_IP_BLOCKS = [
    Network('10.0.0.0/8'), Network('172.16.0.0/12'), Network('192.168.0.0/16')]

PUBLIC_IP_BLOCKS = [
    Network(IP('0.0.0.0'), IP('9.255.255.255')),
    Network(IP('11.0.0.0'), IP('172.15.255.255')),
    Network(IP('172.32.0.0'), IP('192.167.255.255')),
    Network(IP('192.169.0.0'), IP('255.255.255.255'))]
