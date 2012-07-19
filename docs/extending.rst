Extending Serveradmin
=====================

Setting up development environment
----------------------------------

Most steps assume that you are using Debian wheezy, but rumors are that you
could also use Ubuntu.


Creating the virtual environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We will first create a virtual python environment which will isolate our python
packages. This way you can - for example - use different Django versions for
different projects.

Install the debian package ``virtualenvwrapper``::
   
   aptitude install virtualenvwrapper
   
Open a new shell, it will initialize some stuff for the first time. Now you can
create your virtual environment by typing::
   
   mkvirtualenv serveradmin

It will create a folder ``~/.virtualenvs/serveradmin`` with some files for the
environment. You will now see ``(serveradmin)`` in front of your shell prompt
-- this means that you are currently inside the virtual environment ``serveradmin``.

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

If you see a login prompt, use the following user account:
   
   username:
      admin

   password:
      foobar

If not, consult your local Django expert ;)


Bonus: Setting up a cool debugger
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Install ``django-extensions`` and ``werkzeug`` using pip::
   
   pip install django-extensions werkzeug

and add ``'django_extensions'`` to your ``INSTALLED_APPS`` setting in the
``settings.py``.

Now you can use ``./manage.py runserver_plus`` instead of ``./manage.py runserver``
to start the local test webserver with the Werkzeug debugger.

See http://packages.python.org/django-extensions/ for details.


Developing new applications
---------------------------

Code style guideline
^^^^^^^^^^^^^^^^^^^^

First of all, read the Python style guide (`PEP 8 <http://python.org/dev/peps/pep-0008/>`_).
The most important things:

   * Use 4 spaces for indention, **not** tabs
   * Functions and variables use underscores (e.g. ``config_dir``)
   * Classes use CamelCase (e.g. ``NagiosCommit``)
   * Try to keep lines less than 80 chars 


.. warning::
   Ignoring the style guide will make your local Python expert quite sad!


Terminology
^^^^^^^^^^^

Just to have same names:

project:
   Many applications together with settings and a global ``urls.py``
   form a project. The serveradmin is a project.

application (or "app"):
   An application is basically a combination of several files for the same
   topic. You may have an application for nagios, graphs, the servershell etc.
   Applications consist of views, models and templates.


Short git introduction
^^^^^^^^^^^^^^^^^^^^^^

Set your name and email::
   
   git config --global user.name "Your Name"
   git config --global user.email your.name@innogames.de
   
Fetch new changes from remote repository::
   
   git pull

For changes create a new branch, and switch to it::
   
   git branch my_changes
   git checkout my_changes
   
Do your code changes and don't forget to commit often. It's good to commit
even small changes. Before you commit, you have to add files (*even
just modified files*)::

   git add new_file
   git add file_you_have_modified
   git commit

**Don't forget to put a meaningful commit message.**

Once you have done all your changes and your version is ready for deployment
you can merge it back to master. You may want to fetch changes from remote
first::
   
   git checkout master
   git pull # Optionally fetch changes from remote
   git merge my_changes

After merging was successful, you can delete your branch::
   
   git branch -d my_changes
   
It is recommended to do a rebase. This will help to have a clear history::
   
   git rebase
   
And finally push your changes to the remote repository::
   
   git push

Have any changes you don't want to commit and still want to change branch? Use
git stash::
   
   git stash # Will save your uncomitted changes
   # Do whatever you want (e.g. changing branches)
   git stash pop # Will apply changes again and pop it from stash


Short Django introduction
^^^^^^^^^^^^^^^^^^^^^^^^^

If you have some time I recommend doing the `Django Tutorial 
<https://docs.djangoproject.com/en/1.4/intro/tutorial01/>`_. It covers many
topics and gives your a good overview.

For people in a hurry: You will find the serveradmin in the ``serveradmin``
directory while the Remote API (aka. adminapi) is inside ``adminapi``. We will
only cover the serveradmin in this documentation.

Inside the serveradmin you will find the following files:
   
   * ``urls.py``
   * ``settings.py``

The ``settings.py`` contains your settings. You have already edited this file.
Inside the ``urls.py`` you can define URLs for the serveradmin. In most cases
you will have an own ``urls.py`` in your application
