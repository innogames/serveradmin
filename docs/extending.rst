Extending Serveradmin
=====================

Serveradmin is a Django application.  General knowledge about running
Django applications would be useful.


Creating the virtual environment
--------------------------------

We will first create a virtual python environment which will isolate our Python
packages.  This way you can - for example - use different Django versions for
different projects.

Install the debian package ``virtualenvwrapper``::

   aptitude install virtualenvwrapper

Open a new shell, it will initialize some stuff for the first time.  Now you
can create your virtual environment by typing::

   mkvirtualenv serveradmin

It will create a folder ``~/.virtualenvs/serveradmin`` with some files for
the environment. You will now see ``(serveradmin)`` in front of your shell
prompt -- this means that you are currently inside the virtual environment
``serveradmin``.

Every time you want to activate the environment, just type::

   workon serveradmin

For the rest of the instructions we assume that your are inside the serveradmin
virtual environment.

Bonus: You can set up hooks for your virtual environment by editing the files
in ``~/.virtualenvs/serveradmin/bin``.  Using the ``postactivate`` hook you can
change directory to the source code after activating the virtual environment.


Installing dependencies
-----------------------

Most dependencies can be installed by using the ``serveradmin/requirements.txt``
file with pip::

   pip install -r serveradmin/requirements.txt


Setting up the Database
-----------------------
Make sure you use at least the same release of postgresql like serveradmin
You would need a PostgreSQL database to run the application.  PostgreSQL
usually comes by owned by the "postgres" user and the "ident" authentication
enabled.  This means that users on the local system can connect to the server
with their usernames.  You can switch to the "postgres" user and create
a superuser matching your system username to avoid dealing with authentication
again::

   sudo su postgres
   createuser -s myusername

You would also need a database for the application::

    createdb serveradmin

Now you can either create the schema with no data using migrate or import a
dump from an existing data.  The migrate command doesn't work on the first
run for some Django bug, we couldn't fix yet.  Please run it in 2 steps and
ignore the errors emitted by the first one.  To create a new empty schema
you can use::

    python manage.py migrate auth
    python manage.py migrate

If you want to work on the production data, you can dump it from the server,
and restore on your database::

    pg_dump --no-owner --no-privileges --exclude-table-data=sshaccess_state serveradmin > serveradmin.sql
    psql -1 serveradmin < serveradmin.sql


Setting up Django
-----------------

We will copy the example settings to create our local development settings::

   cp serveradmin/settings.example.py serveradmin/settings.py
   vim serveradmin/settings.py

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
---------------------------------

Install ``django-extensions`` and ``werkzeug`` using pip::

   pip install django-extensions werkzeug

and add ``'django_extensions'`` to your ``INSTALLED_APPS`` setting in the
``settings.py``.

Now you can use ``./manage.py runserver_plus`` instead of ``./manage.py runserver``
to start the local test webserver with the Werkzeug debugger.

See http://packages.python.org/django-extensions/ for details.

Code style guideline
--------------------

First of all, read the Python style guide (`PEP 8 <http://python.org/dev/peps/pep-0008/>`_).
The most important things:

   * Use 4 spaces for indention, **not** tabs
   * Functions and variables use underscores (e.g. ``config_dir``)
   * Classes use CamelCase (e.g. ``NagiosCommit``)
   * Try to keep lines less than 80 chars

.. warning::
   Ignoring the style guide will make your local Python expert quite sad!


Terminology
-----------

Just to have same names:

project:
   Many applications together with settings, a global ``urls.py`` and the
   ``manage.py`` form a project. The "serveradmin" is a project.

application (or "app"):
   An application is basically a combination of several files for the same
   topic.  You may have an application for nagios, graphs, the servershell etc.
   Applications consist of views, models and templates.  If you are familiar
   with MVC pattern, think of views being the controllers and the templates
   the views.

models:
   The models will contain your application logic.  This is mostly your database
   structure and operations on on it, but also stuff that's not related to the
   database.  In your application you will find a ``models.py`` where you can
   put your code in.  Django calls a class inheriting ``django.db.models.Model``
   a model, which should not be mistaken for the models itself (e.g. a class
   for your database table and operations vs. your application logic in general)

views:
   The views will get the input from the user and ask the model for the
   execution of operations or fetch data from the model to pass it to the
   template.  As already said, it's known as the controller in the MVC pattern.
   You will add your view functions to the ``views.py`` in your application.

templates:
   The template is - in most cases - just an ordinary HTML file with some
   template markup to display the data it got from the view.  They usually
   reside in a directory named ``yourapp/templates/yourapp``.  You have to
   create it yourself for a new application.


Short git introduction
----------------------

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
you can merge it back to master.  You may want to fetch changes from remote
first::

   git checkout master
   git pull # Optionally fetch changes from remote
   git merge my_changes

After merging was successful, you can delete your branch::

   git branch -d my_changes

It is recommended to do a rebase.  This will help to have a clear history::

   git rebase

And finally push your changes to the remote repository::

   git push

Have any changes you don't want to commit and still want to change branch? Use
git stash::

   git stash # Will save your uncomitted changes
   # Do whatever you want (e.g. changing branches)
   git stash pop # Will apply changes again and pop it from stash


Short Django introduction
-------------------------

If you have some time I recommend doing the `Django Tutorial
<https://docs.djangoproject.com/en/1.8/intro/tutorial01/>`_.  It covers many
topics and gives your a good overview.

For people in a hurry: You will find the Serveradmin in the ``serveradmin``
directory while the Remote API (aka. adminapi) is inside ``adminapi``.  We will
only cover the Serveradmin in this document.

Inside the serveradmin you will find the following files:

   * ``urls.py``
   * ``settings.py``

The ``settings.py`` contains your settings.  You have already edited this file.
Inside the ``urls.py`` you can define URLs for the Serveradmin.  In most cases
you will have an own ``urls.py`` in your application.

We will create a small example application named "secinfo" (for "security
information").  **Please don't commit this application, it is for learning
purposes only!**

We will use the ``manage.py`` to create our application::

   ./manage.py startapp secinfo

Now we have a directory named ``secinfo`` with some files inside it.  We will
move it into the directory ``serveradmin``.

Adding functions to the remote API
----------------------------------

To create new functions which are callable by the Python remote API you have
to define them inside the ``api.py`` file in your application.  If it doesn't
exist, you can just create it.

To export the function you will use the ``api_function`` decorator, as shown
in the following example::

   from serveradmin.api.decorators import api_function

   @api_function(group='example')
   def hello(name):
      return 'Hello {0}!'.format(name)

Now you can call this function remotely::

   from adminapi import api

   example = api.get('example')
   print example.hello('world') # will print 'Hello world!'

The API uses JSON for communication, therefore you can only return and receive
a restricted set of types. The following types are supported: string, integer,
float, bool, dict, list and None.  You can also receive and return datetime/date
objects, but they will be converted to an unix timestamp prior sending. You have
to convert them back manually by using ``datetime.fromtimestamp``.

It has also limited support for exceptions. You can either raise a ``ValueError``
if you get invalid parameters or use ``serveradmin.api.ApiError`` for other
exceptions.  You can subclass ``ApiError`` for more specific exceptions.
Raising exception has also one other restriction: you can only pass a message,
but not additional attributes on the exception.

Look at the following example::

   from serveradmin.api.decorators import api_function
   from serveradmin.api import ApiError

   @api_function(group='example')
   def nagios_downtimes(from_time, to_time):
       if to_time < from_time:
           raise ValueError('From must be smaller than to')

       try:
           return get_nagios_downtimes(from_time, to_time)
       except NagiosError, e:
           # Propagating NagiosError would raise an exception in the
           # serveradmin, but not on the remote side. You have to catch
           # it and reraise it as ApiError or subclass of ApiError
           raise ApiError(e.message)

Handling Permissions
--------------------

We will use Django's integrated Permission system.  In Django, you will define
permissions on a model. You will automatically get a few magic permissions
named ``app_label.(add|change|delete)_modelname``.  For example: if you have
a class ``Bird`` in your application ``bird`` you will get permissions
named ``bird.add_bird`` etc.  If you need own permissions, you have to
define them like this::

   class Bird(models.Model):
       # Fields left out

       class Meta:
          permissions = (
             ('can_fly', 'Can fly'),
          )

You will now get a permission named ``bird.can_fly``.

If you don't have a model class you have to create one.  This will normally
also create a database table, but you can avoid it by setting ``managed``
to ``False``.  This will tell Django that it shouldn't manage the database
for this model.  See the following example::

    class ddosmanager (models.Model):

        class Meta:
            managed = False
            permissions = (
                ('set_state',    'Can enable and disable DDoS Mitigation'),
                ('set_prefixes', 'Can modify prefixes announced to DDoS Mitigation provider'),
                ('view', 'Can view DDoS Mitigation state and prefixes'),
            )

There are several ways to check for permissions at different levels.  To check
permissions on a view, use the ``permission_required`` decorator::

   from django.contrib.auth.decorators import permission_required

   @permission_required('can_view_graphs')
   def view_graphs(request):
       pass # Do some stuff and render template

It will disallow calling this view for all users that don't have the required
permission.

To check permissions in the template you can use the ``perms`` proxy.  Look at
the following example::

   {% if perms.bird.add_bird %}
   <a href="{% url bird_add %}">Add a bird</a>
   {% endif %}

.. warning::
   Just hiding things it the template might not be enough. For example you
   should not hide a form, but leave the view with form processing unchecked.

In the code permissions can be checked using the ``user.has_perm`` method. See
the following example in a view::

   def change_bird(request, name):
       bird = get_object_or_404(Bird, pk=range_id)

       if request.method == 'POST':
          can_delete = request.user.has_perm('bird.delete_bird')
          can_edit = request.user.has_perm('bird.change_bird')
          if action == 'delete' and can_delete:
              bird.delete()
          if action == 'edit' and can_edit:
              pass # edit ip range

To grant permissions to users, use the Django admin interface.  Superusers will
have all permissions be default.

See the `Django documentation on permissions
<https://docs.djangoproject.com/en/1.8/topics/auth/default/#topic-authorization>`_
for details.
