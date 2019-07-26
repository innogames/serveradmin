"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""

import adminapi                                 # NOQA F401
from adminapi import api                        # NOQA F401
from adminapi.dataset import Query, create      # NOQA F401
from adminapi.filters import *                  # NOQA F401 F403
from adminapi.filters import filter_classes
from adminapi.parse import parse_query          # NOQA F401


def help_adminapi():
    help_text = '''
Querying servers:
-----------------

We want to find all servers with game_world greater 10:

   servers = Query({'game_world': GreaterThan(10)})

Available filters: {filters}

Changing servers:
-----------------

Changing game_function to "web" to all servers:

   for server in servers:
       server['game_function'] = 'web'

      or

   servers.update(game_function='web')

   servers.print_changes()
   servers.commit()


Calling API functions:
----------------------

Get the information of an IP range as dictionary:

   ip_api = api.get('ip')
   print ip_api.get_range('af01.admin')


Parsing an query:
-----------------

Parse an query from the servershell and return the arguments for the
query function.

   query_args = parse_query('servertype=ds game_world=comparison(> 10)')
   servers = Query(query_args)
'''
    print(help_text.format(filters=', '.join(
        f.__name__ for f in filter_classes
    )))
    print()


print('+--------------------------------------------+')
print('|                                            |')
print('|    Welcome to the interactive adminapi!    |')
print('|                                            |')
print('|  Type help_adminapi() to print some help.  |')
print('|                                            |')
print('+--+--------------------------------------+--+')
print('   | Please note that this module is only |   ')
print('   |   for use in an interactive shell!   |   ')
print('   +--------------------------------------+   ')
