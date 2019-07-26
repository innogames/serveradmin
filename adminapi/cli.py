"""Serveradmin - adminapi - Command Line Interface

Copyright (c) 2019 InnoGames GmbH
"""

from __future__ import print_function

from argparse import ArgumentParser, ArgumentTypeError

from adminapi.dataset import Query
from adminapi.parse import parse_query


def parse_args():
    multi_note = ' (can be specified multiple times)'
    parser = ArgumentParser('adminapi')
    parser.add_argument('query', nargs='+')
    parser.add_argument(
        '-1',
        '--one',
        action='store_true',
        help='Make sure exactly one server matches with the query',
    )
    parser.add_argument(
        '-a',
        '--attr',
        action='append',
        help='Attributes to fetch (default: "hostname")' + multi_note,
    )
    parser.add_argument(
        '-o',
        '--order',
        action='append',
        help='Attributes to order by the result' + multi_note,
    )
    parser.add_argument(
        '-r',
        '--reset',
        action='append',
        help='Multi attributes to reset' + multi_note,
    )
    parser.add_argument(
        '-u',
        '--update',
        type=attr_value,
        action='append',
        help='Attributes with values to update' + multi_note,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    attribute_ids_to_print = args.attr if args.attr else ['hostname']
    attribute_ids_to_fetch = list(attribute_ids_to_print)
    if args.reset:
        attribute_ids_to_fetch.extend(args.reset)
    if args.update:
        attribute_ids_to_fetch.extend(u[0] for u in args.update)

    # TODO: Avoid .join()
    filters = parse_query(' '.join(args.query))
    query = Query(filters, attribute_ids_to_fetch, args.order)

    if args.one and len(query) > 1:
        raise Exception(
            'Expecting exactly one server, found {} servers'
            .format(len(query))
        )

    for server in query:
        if args.reset:
            apply_resets(server, args.reset)
        if args.update:
            apply_updates(server, args.update)
        print_server(server, attribute_ids_to_print)
    if args.reset or args.update:
        query.commit()


def attr_value(arg):
    arg_split = tuple(arg.split('='))
    if len(arg_split) != 2:
        raise ArgumentTypeError('You need to pass an attribute=value')
    return arg_split


def apply_resets(server, attribute_ids):
    for attribute_id in attribute_ids:
        server[attribute_id].clear()


def apply_updates(server, attribute_values):
    for attribute_id, value in attribute_values:
        server.set(attribute_id, value)


def print_server(server, attribute_ids):
    values = []
    for attribute_id in attribute_ids:
        if attribute_id not in server:
            values.append('{N/A}')
            continue

        value = server[attribute_id]
        if any(value is v for v in (None, True, False)):
            value = '{{{}}}'.format(str(value).lower())

        values.append(value)

    print(*values, sep='\t')
