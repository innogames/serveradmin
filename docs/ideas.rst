Ideas
=====

Misc
----

* Revert auth token char set to [a-zA-Z0-9]
* more will follow

API for bash scripts
--------------------

All scripts will look for the user who actually executed the script by
traversing the process tree to load the rcfile for him.

All scripts take parameter ``-t`` for auth token. This has precedence
over the auth token in the rcfile.

Querying for servers::
   
   # Query term works like the search in servershell. It will print
   # the hostnames, one per line.
   adminapi_query 'game_function=web'

   # You can also get multiple attributes. They are separated by tabs.
   adminapi_query 'os=Not(lenny)' -a hostname -a os

Committing changes to servers::
   # Change two servers
   adminapi_commit 'host1 os=squeeze game_function=db host2 os=wheezy'
   
   # Remove and add values to multi attributes
   adminapi_commit 'host1 additional_ips=-127.0.0.1 additional_ips=+192.168.0.1'

Creating new server::
  
   # Simple create
   adminapi_create hostname=foobar servertype=test intern_ip=127.0.0.1

   # To set multi attributes just list the attribute several times
   adminapi_create hostname=foobar [...] webserver=nginx webserver=apache2
