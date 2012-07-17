Extending Serveradmin
=====================

Setting up development environment
----------------------------------

Most steps assume that you are using Debian wheezy, but rumors are that you
could also use Ubuntu.


Creating virtual environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We will first create a virtual python environment which will isolate our python
packages. This way you can for example use different Django versions for
different projects.

Install the debian package ``virtualenvwrapper``::
   
   aptitude install virtualenvwrapper
   
Open a new shell, it will initialize some stuff for the first time. Now you can
create your virtual environment by typing::
   
   mkvirtualenv serveradmin

It will create a folder ``~/.virtualenvs/serveradmin`` with some files for the
environment. You will now see ``(serveradmin)`` in your shell prompt -- this
means that you are currently inside the virtual environment ``serveradmin``.

Every time you want to activate the environment, just type::
   
   workon serveradmin

For the rest of the instructions we assume that your are inside the serveradmin
virtual environment.


Installing dependencies
^^^^^^^^^^^^^^^^^^^^^^^

Most dependencies can be installed by using the ``requirements.txt`` file for
pip::
   
   pip install -r requirements.txt

The only exception is ``MySQLdb``, which could of course also be installed
using pip, but it requires some development headers and compilation. To
avoid this, just install the debian package and symlink it to the virtual
environment::
   
   aptitude install python-mysqldb
   cd ~/.virtualenv/serveradmin/lib/python2.7/site-packages
   ln -s /usr/lib/pyshared/python2.7/_mysql.so
   ln -s /usr/share/pyshared/_mysql_exceptions.py
   ln -s /usr/share/pyshared/MySQLdb


Setting up Django
^^^^^^^^^^^^^^^^^

We will copy the example settings to create our local development settings::
   
   cp serveradmin/settings.py.example serveradmin/settings.py
   vim serveradmin/settings.py
   
For development you just need to change ``DATABASES['default']['PASSWORD']``.
We will use an example database running on ``serveradmin.admin``. It contains
(and older) dump of the real production database. You will get the password
on ``serveradmin.admin``::
   
   ssh serveradmin.admin cat /opt/serveradmin/.mysql-access.txt

The MySQL server is only reachable inside the datacenter, use VPN or build a
cheap SSH tunnel::
   
   ssh -L 3306:serveradmin.admin:3306 control.innogames.net

When editing the config, don't forget to remove the exception at the end.

To check whether your setup was successful, you can run the integrated test
webserver::
   
   ./manage.py runserver

and point your browser to http://localhost:8000/.


Bonus: Setting up cool debugger
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Install ``django-extensions`` and ``werkzeug`` using pip::
   
   pip install django-extensions werkzeug

and add ``'django_extensions'`` to your ``INSTALLED_APPS`` setting in the
``settings.py``.

Now you can use ``./manage.py runserver_plus`` instead of ``./manage.py runserver``
to start the local test webserver with the Werkzeug debugger.

See http://packages.python.org/django-extensions/ for details.


Developing new applications
---------------------------
