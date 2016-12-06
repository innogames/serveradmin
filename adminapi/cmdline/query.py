#!/usr/bin/python
from __future__ import print_function

import sys
from optparse import OptionParser

from adminapi.dataset import query, filters
from adminapi.dataset.base import MultiAttr
from adminapi.utils.parse import parse_query


def main():
    opt_parser = OptionParser()
    opt_parser.add_option('-a', '--attr', dest='attrs', action='append')
    opt_parser.add_option('-n', '--null', dest='null_value', default='-')
    opt_parser.add_option('-e', '--export', action='store_true')
    opt_parser.add_option('-o', '--orderby', dest='orderby', action='append')
    opt_parser.add_option('-s', '--separator', dest='separator', default=' ')

    options, args = opt_parser.parse_args()

    if len(args) < 1:
        print('You have to supply a search term.', file=sys.stderr)
        sys.exit(1)

    attrs = options.attrs if options.attrs else ('hostname', )
    orderby = options.orderby if options.orderby else ('hostname', )
    host_list = query(
        **parse_query(' '.join(args), filter_classes=filters.filter_classes)
    ).restrict(*attrs).order_by(*orderby).fetch_now()

    if options.export:
        print(options.separator.join(host[attrs[0]] for host in host_list))
        exit(0)

    for host in host_list:
        row_values = []
        for attr in attrs:
            if attr in host:
                row_values.append(format_obj(host[attr]))
            else:
                row_values.append(options.null_value)
        print(u'\t'.join(row_values))


def format_obj(obj):
    if isinstance(obj, MultiAttr):
        return ', '.join(sorted(str(x) for x in obj))
    return str(obj)


if __name__ == '__main__':
    main()
