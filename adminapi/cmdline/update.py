#!/usr/bin/env python
from __future__ import print_function

import sys
import ipaddress
import argparse
from distutils.util import strtobool
from adminapi.dataset import query, filters, base
from adminapi.utils import format_obj
from adminapi.utils.parse import parse_query
from adminapi.cmdline.utils import get_auth_token


def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('hostname', help = 'Host on which changes need to be performed in serveradmin')
    parser.add_argument('attrs', nargs = '+', help = '')
    parser.add_argument('-o', '--overwrite', dest = 'overwrite', action = 'store_true', help = 'Overwrite multi attributes')
    args=parser.parse_args()

    if not args.hostname:
        print('You need to pass a hostname', file = sys.stderr)
        sys.exit(1)

    if not update(args.hostname, args.attrs, args.overwrite):
        sys.exit(1)


def update(hostname, attrs, overwrite):
    host = query(hostname = hostname).get()
    for attr_value in attrs:
        if len(attr_value.split('=')) != 2:
            print('You need to pass an attribute=value', file=sys.stderr)
            return False
        attr, value = attr_value.split('=')
        if type(host[attr]) is base.MultiAttr:
            if overwrite:
                host[attr] = set([value])
            else:
                host[attr].add(value)
        elif type(host[attr]) is bool:
            host[attr] = strtobool(value)
        elif type(host[attr]) is int:
            host[attr] = int(value)
        else:
                host[attr] = value
    host.commit()


if __name__ == '__main__':
    main()
