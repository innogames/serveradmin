from __future__ import print_function
import sys
from itertools import izip

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
        return ', '.join(obj)
    else:
        return unicode(obj)

def print_heading(heading, char='-', file=sys.stdout):
    print('{0}\n{1}\n'.format(heading, char * len(heading)),
            file=file)

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

    def as_ip(self):
        ip = [0] * 4
        ip_int = self.ip
        for i in xrange(4):
            ip[i] = str(ip_int & 0xff)
            ip_int = ip_int >> 8
        
        return '.'.join(reversed(ip))

    def as_int(self):
        return self.ip

    def is_internal(self):
        return any(start <= self.ip <= end for start, end in PRIVATE_IP_BLOCKS)

    def is_public(self):
        return not self.is_internal()

# http://en.wikipedia.org/wiki/Private_network
PRIVATE_IP_BLOCKS = [
    (IP('10.0.0.0').as_int(),  IP('10.255.255.255').as_int()),
    (IP('172.16.0.0').as_int(), IP('172.31.255.255').as_int()),
    (IP('192.168.0.0').as_int(), IP('192.168.255.255').as_int())
]
