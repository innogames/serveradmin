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

You can use the :class:`adminapi.dataset.Query` function to find servers which
match certain criteria.  See the following example which will find all
webservers of Tribal Wars::

    from adminapi.dataset import Query

    hosts = Query({'servertype': 'vm', 'game_function': 'web'})

    for host in hosts:
        print host['hostname']

The Query class takes keyword arguments which contain the filter conditions.
Each key is an attribute of the server while the value is the value that must
match. You can either use strings, integers or booleans for exact value matching.
All filter conditions will be ANDed.

More often you need filtering with more complex conditions, for example regular
expression matching, comparison (less than, greater than) etc.  For this kind
of queries there is a filters modules which defines some filters you can use.
The following example will give you all Tribal Wars webservers, which world
number is between 20 and 30::

    from adminapi.filters import All, GreaterThan, LessThan

    hosts = Query({
        'servertype': 'vm',
        'game_function': 'web',
        'game_world': All(GreaterThan(20), LessThan(30)),
    })


Accessing and modifying attributes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each server is represented by a server object which allows a dictionary-like
access to their attributes. This means you will have the usual behaviour of
a dictionary with methods like ``keys()``, ``values()``, ``update(...)`` etc.

You can get server objects by iterating over a query or by calling
``get()`` on the query.  Changes to the attributes are not directly
committed.  To commit them you must call ``commit()`` on the query.

Here is an example which cancels all servers for Seven Lands::

    hosts = Query({'servertype': 'hardware'})
    for host in hosts:
        hosts['canceled'] = True
    hosts.commit()

Another example will print all attributes of the techerror server and check
for the existence of the ``game_function`` attribute::

    techerror = Query({'hostname': 'techerror.support.ig.local'}).get()
    for attr, value in techerror.items(): # Iterate like a dict!
         print "{0}={1}".format(key, value)

    if 'game_function' in techerror:
         print "Something is wrong!"

Multi attributes are stored as instances of :class:`MultiAttr`, which is a
subclass of set. Take a look at :class:`set` for the available methods. See the
following example which iterates over all additional IPs and adds another one::

    techerror = Query({'hostname': 'techerror.support.ig.local'}).get()
    for ip in techerror['additional_ips']:
         print ip
    techerror['additional_ips'].add('127.0.0.1')

.. warning::
    Modifying attributes of a server object that is marked for deleting will
    raise an exception. The ``update()`` function will skip servers that
    are marked for deletion.

Query Reference
^^^^^^^^^^^^^^^

The :class:`adminapi.dataset.Query` function returns a query object that
supports iteration and some additional methods.

.. class:: Query

    .. method:: Query.__iter__()

        Return an iterator that can be used to iterate over the query.
        The result itself is cached, iterating several times will not hit
        thedatabase again.  You usually don't call this function directly,
        but use the class' object in a for-loop.

    .. method:: Query.__len__()

        Return the number of servers that where returned. This will fetch all
        results.

    .. method:: get()

        Return the first server in the query, but only if there is just one
        server in the query.  Otherwise, you will get an exception.
        #FIXME: Decide kind of exception

    .. method:: commit_state()

        Return the state of the object.

    .. method:: commit()

        Commit the changes that were done by modifying the attributes of
        servers in the query.  Please note: This will only affect
        servers that were accessed through this query!

    .. method:: rollback()

        Rollback all changes on all servers in the query.  If the server is
        marked for deletion, this will be undone too.

    .. method:: delete()

        Marks all server in the query for deletion.  You need to commit
        to execute the deletion.

        .. warning::
            This is a weapon of mass destruction. Test your script carefully
            before using this method!

    .. method:: update(**attrs)

        Mass update for all servers in the query using keyword args.
        Example: You want to cancel all Seven Land servers::

            Query({'servertype': 'hardware'}).update(canceled=True)

        This method will skip servers that are marked for deletion.

        You still have to commit this change.

.. *** this line fixes vim syntax highlighting

Server object reference
^^^^^^^^^^^^^^^^^^^^^^^

The reference will only include the additional methods of the server object.
For documentation of the dictionary-like access see :class:`dict`.

.. class:: DatasetObject

    .. attribute:: old_values

        Dictionary which contains the values of the attributes before
        they were changed.

    .. method:: is_dirty()

        Return True, if the server object has uncomitted changes, False
        otherwise.

    .. method:: is_deleted()

        Return True, if the server object is marked for deletion.

    .. method:: delete()

        Mark the server for deletion. You need to commit to delete it.

.. *** this line fixes vim syntax highlighting

Creating servers
----------------

The function :func:`adminapi.dataset.create` allows you to create new servers:

.. function:: create(attributes)

    :param attributes: A dictionary with the attributes of the server.
    :return: The server (``DatasetObject``) that was created with all attributes
             (given and filled attributes)

Making API calls
----------------

API calls are split into several groups. To call a method you need to get a
group object first. See the following example for getting a free IP::

    # Do authentication first as described in section "Authentication"
    from adminapi import api

    ip = api.get('ip')
    free_ip = ip.get_free('af03.ds.fr', reserve_ip=False)

You will find a list of available API functions in the admin tool.
