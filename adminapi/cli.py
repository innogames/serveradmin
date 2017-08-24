"""igserver - The command line interface

Copyright (c) 2017, InnoGames GmbH
"""

from __future__ import print_function

from argparse import ArgumentParser, ArgumentTypeError

from adminapi import _api_settings
from adminapi.dataset import QuerySet
from adminapi.utils.parse import parse_query


def parse_args():
    parser = ArgumentParser('igserver')
    parser.add_argument('query', nargs='+')
    parser.add_argument(
        '-1',
        '--one',
        action='store_true',
        help='Make sure exactly one server matches with the query',
    )
    parser.add_argument(
        '-a',
        '--attrs',
        nargs='+',
        default=['hostname'],
        help='The attributes to fetch',
    )
    parser.add_argument(
        '-o',
        '--order',
        nargs='+',
        default=['hostname'],
        help='Attributes to order by the result',
    )
    parser.add_argument(
        '-r',
        '--reset',
        nargs='+',
        default=[],
        help='Reset multi attributes',
    )
    parser.add_argument(
        '-u',
        '--update',
        nargs='+',
        type=attr_value,
        default=[],
        help='The attributes to update',
    )

    return parser.parse_args()


def main():
    args = parse_args()
    servers = (
        QuerySet(
            # TODO: Avoid .join()
            filters=parse_query(' '.join(args.query)),
            auth_token=_api_settings['auth_token'],
            timeout=_api_settings['timeout_dataset'],
        )
        .restrict(*(args.attrs + args.reset + [k for k, v in args.update]))
        .order_by(*args.order)
    )

    if args.one and len(servers) > 1:
        raise Exception(
            'Expecting exactly one server, found {} servers'
            .format(len(servers))
        )

    changes = bool(args.reset or args.update)
    for server in servers:
        if changes:
            apply_changes(server, args.reset, args.update)
        print_server(server, args.attrs)
    if changes:
        servers.commit()


def attr_value(arg):
    arg_split = tuple(arg.split('='))
    if len(arg_split) != 2:
        raise ArgumentTypeError('You need to pass an attribute=value')
    return arg_split


def apply_changes(server, reset, update):
    for attribute_id in reset:
        server[attribute_id].clear()
    for attribute_id, value in update:
        server.set(attribute_id, value)


def print_server(server, attribute_ids):
    values = []
    for attribute_id in attribute_ids:
        if attribute_id not in server:
            values.append('{N/A}')
            continue

        value = server[attribute_id]

        # Temporary hack
        if attribute_id == 'hostname':
            if not any(value.endswith(d) for d in [
                '.ig.local',
                '.innogames.net',
            ]):
                value += '.ig.local'

        if value in [None, True, False]:
            value = '{{{}}}'.format(str(value).lower())

        values.append(value)

    print(*values, sep='\t')
