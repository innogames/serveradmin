#!/usr/bin/python
from __future__ import print_function

import sys
from optparse import OptionParser

import adminapi
from adminapi.dataset import query, filters, DatasetError
from adminapi.utils import format_obj
from adminapi.utils.parse import parse_query
from adminapi.cmdline.utils import get_auth_token

def main():
    opt_parser = OptionParser()
    opt_parser.add_option('-a', '--attr', dest='attrs', action='append')
    opt_parser.add_option('-t', '--token', dest='token')
    opt_parser.add_option('-n', '--null', dest='null_value', default='-')
    opt_parser.add_option('-e', '--export', action='store_true')
    opt_parser.add_option('-s', '--separator', dest='separator', default=' ')

    options, args = opt_parser.parse_args()

    if len(args) != 1:
        print('You have to supply a search term.', file=sys.stderr)
        sys.exit(1)
    
    if options.token:
        auth_token = options.token
    else:
        auth_token = get_auth_token()

    if auth_token is None:
        print('No auth token found.', file=sys.stderr)
        print('Use -t auth_token or create ~/.adminapirc', file=sys.stderr)
        sys.exit(1)

    attrs = options.attrs if options.attrs else ['hostname']

    adminapi.auth(auth_token)

    try:
        query_args = parse_query(args[0],
                filter_classes=filters.filter_classes)
    except ValueError, e:
        print(unicode(e), file=sys.stderr)
        sys.exit(1)
    
    if not attrs:
        attrs = ['hostname']
    
    try:
        q = query(**query_args).restrict(*attrs).request_results()
    except (ValueError, DatasetError), e:
        print(unicode(e), file=sys.stderr)
        sys.exit(1)

    if options.export:
        print(options.separator.join(host[attrs[0]] for host in q))
        exit(0)

    for host in q:
        row_values = []
        for attr in attrs:
            if attr in host:
                row_values.append(format_obj(host[attr]))
            else:
                row_values.append(options.null_value)
        print(u'\t'.join(row_values))
    sys.exit(0)

if __name__ == '__main__':
    main()
