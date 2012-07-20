Python Remote API
=================

The adminapi provides a python module which can talk to the serveradmin via an
API. It provides functions for querying servers, modifying their attributes,
triggering actions (e.g. committing nagios) etc.

.. warning::
   This is only a draft. The API might change.

Authentication
--------------

Every script that uses the module must authorize itself before using the API.
You need to generate an authentication token for your script in the web
interface of the serveradmin. This has several benefits over using a generic
password:

* Logging changes that were done by a specific script
* Providing a list with existing scripts which are using the API
* Possibility to withdrawn an authentication token without changing every script.

To authenticate your script you need to import the module and call the auth
function before doing any API calls::
   
   import adminapi

   adminapi.auth('yourScriptsAuthToken')

Querying and modifying servers
------------------------------

Using the ``dataset`` module you can filter servers by given criteria and
modify their attributes.

Basic queries
^^^^^^^^^^^^^

You can use the :func:`adminapi.dataset.query` function to find servers which
match certain criterias. See the following example which will find all
webservers of Tribal Wars::
   
   import adminapi
   from adminapi.dataset import query
   
   adminapi.auth('yourScriptsAuthToken')

   hosts = query(servertype='ds', game_function='web')

   for host in hosts:
       print host['hostname']
   
The query function takes keyword arguments which contain the filter conditions.
Each key is an attribute of the server while the value is the value that must
match. You can either use strings, integers or booleans for exact value matching.
All filter conditions will be ANDed.

More often you need filtering with more complex conditions, for example regular
expression matching, comparism (less than, greating than) etc. For this kind
of queries there is a filters modules which defines some filters you can use.
The following example will give you all Tribal Wars webservers, which world
number is between 20 and 30::
   
   # see above for usual imports and authentication
   from adminapi.dataset import filters

   hosts = query(servertype='ds', game_function='web', game_world=
          filters.GreaterEqual(20) and filters.GreaterEqual(30))

The following filters are available:

:class:`adminapi.dataset.filters.Regexp`
   Filters the attribute by matching a regular expression. Use this sparingly
   because it requires a sequence scan over the dataset.

:class:`adminapi.dataset.filters.Comparism`
   Implement simple comparism functions. The first argument is the comparism
   operator (one of ``<``, ``>``, ``>=`` and ``<=``) and the second is the
   value that should be compared. ``game_world=Comparism('<' 20)`` will be
   evaluated as ``game_world < 20``.

:class:`adminapi.dataset.filters.Any`
   If you want to check whether an attribute is *any* of the mentioned
   values. For example if you want to check whether the servers is running
   lenny or squeeze (or theoretically both, it the attribute has multiple
   values) you will write::
      
      hosts = query(os=filters.Any('lenny', 'squeeze'))

   If you have a list with accepted values, just use Python's builtin arg
   expansion::
      
      possible_os = ['lenny', 'squeeze']
      hosts = query(os=filters.Any(*possible_os))
      
:class:`adminapi.dataset.filters.InsideNetwork`
   Checks if an IP is inside a network. It takes one or more ``Network``
   objects. If several networks are given, it checks if it's inside any
   network. See the following example::
      
      query(all_ips=filters.InsideNetwork(Network('192.168.0.0/24')))

:class:`adminapi.dataset.filters.PublicIP`
   Checks for public IP

:class:`adminapi.dataset.filters.PrivateIP`
   Checks for private IP

:class:`adminapi.dataset.filters.And`
   Combines two or more filters by using the conjunction of them. Every filter
   also implements ``__and__``, which allows you to just write ``and`` between
   two filters.

:class:`adminapi.dataset.filters.Or`
   Combines two or more filters by using the disjunction of them. Every filter
   also implements ``__or__``, which allows you to just write ``or`` between
   two filters.

:class:`adminapi.dataset.filters.Not`
   Negates the given filter or value.

:class:`adminapi.dataset.filters.Between`
   Shorthand for ``filters.And(filters.Comparism('>=', a), filters.Comparism('<=', b))``

:class:`adminapi.dataset.filters.Optional`
   Normally, if you filter for an attribute the filter will evaluate to False
   of the attribute does not exist on the server. Using ``Optional`` the
   filter will evaluate to True, if the argument does not exist. This must
   always be the outer filter.

.. _python-api-augmenting:

Augmenting
^^^^^^^^^^

Sometimes you might want additional information about servers that are not
stored in their attributes. In this case you need to augment the query. This
simply means that the servers will get additional attributes that can be
read but can not be changed. You will simply call ``augment`` on the query
result before using it.

The following augmentations are not available yet, but might be in future:

servermonitor
   Adds the following attributes to the server if applicable:
   
   * cpu_hourly
   * cpu_daily
   * io_hourly
   * io_daily
   * disk_free
   * mem_free

You can also use additional attributes in your query for filtering, but be
aware: They are filtered in Python and not on the database level (which is not
possible).


Magic attributes
^^^^^^^^^^^^^^^^

Magic attributes are attributes that do not exist but are generated on the
fly. They can only be used for filtering and don't appear in the attributes
itself.

The following magic attributes are available:

all_ips
   Combines all available IPs for the server. This includes internal and
   public IPs.


Accessing and modifying attributes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each server is represented by a server object which allows a dictionary-like
access to their attributes. This means you will have the usual behaviour of
a dictionary with methods like ``keys()``, ``values()``, ``update(...)`` etc.

You can get server objects by iterating over a query set or by calling
``get()`` on the query set. Changes to the attributes are not directly
committed. To commit them you must either call ``commit()`` on the server
object or on the query set. For performance reasons, use ``commit()`` on the
query set if you change many servers rather than calling ``commit()`` on every
server object. You can also use the ``update()`` method on the query set for
mass updates.

Here is an example which cancels all servers for Seven Lands::
   
   # BAD WAY! DON'T DO THIS!
   # It will send a HTTP request for every server!
   hosts = query(servertype='sl')
   for host in hosts:
       host['canceled'] = True
       host.commit()

   # GOOD WAY:
   hosts = query(servertype='sl')
   for host in hosts:
      hosts['canceled'] = True
   hosts.commit()

   # EVEN BETTER WAY:
   query(servertype='sl').update(canceled=True).commit()

Another example will print all attributes of the techerror server and check
for the existence of the ``game_function`` attribute::
   
   techerror = query(hostname='techerror.support').get()
   for attr, value in techerror.items(): # Iterate like a dict!
       print "{0}={1}".format(key, value)

   if 'game_function' in techerror:
       print "Something is wrong!" 

Multi attributes are stored as instances of :class:`MultiAttr`, which is a
subclass of set. Take a look at :class:`set` for the available methods. See the
following example which iterates over all additional IPs and adds another one::
   
   techerror = query(hostname='techerror.support').get()
   for ip in techerror['additional_ips']:
       print ip
   techerror['additional_ips'].add('127.0.0.1')

.. warning::
   Modifying attributes of a server object that is marked for deleting will
   raise an exception. The ``update()`` function will skip servers that
   are marked for deletion.

Query set reference
^^^^^^^^^^^^^^^^^^^

The :func:`adminapi.dataset.query` function returns a query set object that
supports iteration and some additional methods.

.. class:: QuerySet
   
   .. method:: QuerySet.__iter__()
      
      Return an iterator that can be used to iterate over the query set. The
      result itself is cached, iterating several times will not hit the
      database again. You usually don't call this function directly but use
      the class' object in a for-loop.

   .. method:: QuerySet.__len__()
      
      Return the number of servers that where returned. This will fetch all
      results, use ``count()`` if you just want the number but not any
      results.

   .. method:: augment(*augmentations)
      
      This will augment the query set by additional attributes. See
      :ref:`python-api-augmenting`

   .. method:: restrict(*attrs)
      
      Use this method to only load a restricted set of attributes. This can be
      done for performance reasons. Note: You need to fetch the attributes
      you want to change e.g. add them to the arguments of this methods.
      See the following example, which will only fetch hostname and internal
      ip for all servers::
         
         hosts = query().restrict('hostname', 'internal_ip')

   .. method:: count()

      Return the number of servers that are matched by the query. Does not
      fetch the results.

   .. method:: get()
      
      Return the first server in the query set but only if there is just one
      server in the query set. Otherwise you will get an exception.
      #FIXME: Decide kind of exception
   
   .. method:: is_dirty()
      
      Return True, if the query set contains a server object which has
      uncomitted changes, False otherwise.

   .. method:: commit(skip_validation=False, force_changes=False)
      
      Commit the changes that were done by modifying the attributes of
      servers in the query set. Please note: This will only affect
      servers that were accessed through this query set!

      If ``skip_validation`` is ``True`` it will neither validate regular
      expressions nor whether the attribute is required.

      If ``force_changes`` is ``True`` it will overrride any changes
      which were done in the meantime.
   
   .. method:: rollback()
      
      Rollback all changes on all servers in the query set. If the server is
      marked for deletion, this will be undone too.

   .. method:: delete()
      
      Marks all server in the query set for deletion. You need to commit
      to execute the deletion.

      .. warning::
         This is a weapon of mass destruction. Test your script carefully
         before using this method!

   .. method:: update(**attrs)
      
      Mass update for all servers in the query set using keyword args.
      Example: You want to cancel all Seven Land servers::
         
         query(servertype='sl').update(canceled=True)

      This method will skip servers that are marked for deletion.

      You still have to commit this change.

   .. method:: print_list(attr='hostname', file=sys.stdout)
      
      Print a list with all servers in the query set. This will look like::

      * en1db.gp
      * en2db.gp
      * en3db.gp

   .. method:: print_table(*attrs, file=sys.stdout)
   
      Print a table with given attributes, for example::
      
         query(servertype='ds').print_table('hostname', 'game_function')

      will print the following table::
         
         +-----------+---------------+
         | hostname  | game_function |
         +-----------+---------------+
         | ae0db1.ds | db1           |
         | ae0l1.ds  | web           |
         | ae0l2.ds  | web           |
         +-----------+---------------+

   .. method:: print_changes(title=lambda x: x['hostname'], file=sys.stdout)
      
      Prints all changes of all servers in this query set. For the behavior
      of title, see :func:`ServerObject.print_changes`.

      Example output after changing ``os`` to ``squeeze``::
         
         techerror.support
         -----------------
         
         +-----------+-----------+-----------+
         | Attribute | Old value | New value |
         +-----------+-----------+-----------+
         | os        | lenny     | squeeze   |
         +-----------+-----------+-----------+

.. *** this line fixes vim syntax highlighting

Server object reference
^^^^^^^^^^^^^^^^^^^^^^^

The reference will only include the additional methods of the server object.
For documentation of the dictionary-like access see :class:`dict`.

.. class:: ServerObject

   .. attribute:: old_values
      
      Dictionary which contains the values of the attributes before
      they were changed.
   
   .. method:: is_dirty()
      
      Return True, if the server object has uncomitted changes, False
      otherwise.

   .. method:: is_deleted()
      
      Return True, if the server object is marked for deletion.
   
   .. method:: commit(skip_validation=False, force_changes=False)
      
      Commit changes that were done in this server object. See documentation
      on the queryset for ``skip_validation`` and ``force_changes``.

   .. method:: rollback()
      
      Rollback all changes on the server object. If the server is marked for
      deletion, this will be undone too.

   .. method:: delete()

      Mark the server for deletion. You need to commit to delete it.

   .. method:: print_table(*attrs, file=sys.stdout)
      
      Print a table with with given attributes. If no arguments are given,
      then all attributes are used. Example::
         
         +-----------+-------------------+
         | Attribute | Value             |
         +-----------+-------------------+
         | hostname  | techerror.support |
         | os        | lenny             |
         |         [...]                 |
         | webserver | nginx             |
         +-----------+-------------------+

   .. method:: print_changes(title=None, file=sys.stdout)
      
      Prints all changes of the server object, for example::
      
         techerror = query(hostname='techerror.support').get()
         techerror['os'] = 'squeeze'
         techerror.print_changes()

      will print::
         
         +-----------+-----------+-----------+
         | Attribute | Old value | New value |
         +-----------+-----------+-----------+
         | os        | lenny     | squeeze   |
         +-----------+-----------+-----------+

      Title can be either a string, a function or ``None``. If it is a string
      it will simply print it. If it is a function it calls the function with
      the server object as argument and expects a string as return value which
      will be printed. If title is ``None``, no title will be printed.

      Please note: There are no changes after committing!

.. *** this line fixes vim syntax highlighting

Creating servers
----------------

The function :func:`adminapi.dataset.create` allows you to create new servers:

.. function:: create(attributes, skip_validation=False, fill_defaults=True, fill_defaults_all=False)
   
   :param attributes: A dictionary with the attributes of the server.
   :param skip_validation: Will skip regular expression and required validation.
   :param fill_defaults: Automatically fill it the default if the attribute is
                         required.
   :param fill_defaults_all: Like ``fill_defaults``, but also fill attributes
                             with defaults which are not required.
   :return: The server (``ServerObject``) that was created with all attributes
            (given and filled attributes)

Making API calls
----------------

API calls are split into several groups. To call a method you need to get a
group object first. See the following example for getting a free IP::
   
   # Do authentication first as described in section "Authentication"
   from adminapi import api

   ip = api.get('ip')
   free_ip = ip.get_free('af03.ds.fr', reserve=False)

You will find a list of available API functions in the admin tool.
