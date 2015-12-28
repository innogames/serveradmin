from __future__ import print_function

from adminapi.dataset import query, filters, create
from adminapi.dataset.filters import *
from adminapi.utils.parse import parse_query
from adminapi import api

import adminapi

adminapi.auth()

def help_adminapi():
    help_text = """
Querying servers:
-----------------

We want to find all servers of tribal wars with game_world greater 10:

   servers = query(servertype='ds', game_world=Comparison('>', 10))
      or
   servers = query(servertype='ds', game_world=filters.Comparison('>', 10)

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
   servers = query(**query_args)


    """.strip()
    print(help_text.format(filters=', '.join(filter_classes.keys())))
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
print('                                              ')
