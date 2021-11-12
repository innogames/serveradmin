Extending Serveradmin
=====================

Serveradmin is a Django application.  General knowledge about running
Django applications would be useful.


Running Serveradmin
-------------------

We provide a docker-compose setup that gives you a local development instance
with 2 commands.

First make sure you have docker-compose installed as described
`here <https://docs.docker.com/compose/install/>`_.

Then run these two commands::

    cp .env.dist .env
    docker-compose up

The default values in .env.dist are sufficient however feel free to adjust
them to your needs.

You can access the web service to execute Django commands and run scripts::

    docker-compose exec web

    # Example: Run Django management commands
    pipenv run python -m serveradmin -h

    # Example: Use the Python Remote API
    pipenv run python -m adminapi "hostname=example.com"


**Tip**

You may still want to have a virtual environment for Serveradmin on your
host machines and run pipenv install -D to have all modules available for your
IDEs auto completion etc.


Database Dump
-------------

If you have a running instance of Serveradmin which is reachable via SSH you
can update the PRODUCTION_DB variable in .env to your database host and run
dump.sh from your **host** machine::

    # .env
    PRODUCTION_DB=your-serveradmin-db-host.example.com

    # Execute on host
    ./dump.sh


Testing your changes
--------------------

We have some tests which are executed when making a PR that you can already
run locally to check if your changes are breaking anything existing. They are
far from comprehensive at the time of writing this but can safe you some
manual testing.

You can execute the tests with the following commands

    # Tests for the commandline interface: adminapi
    pipenv run python -m unittest discover adminapi -v

    # Tests for the backend code
    pipenv run python -Wall -m serveradmin test --noinput --parallel


Bonus: Setting up a cool debugger
---------------------------------

Install ``django-extensions`` and ``werkzeug`` using pip::

    pip install django-extensions werkzeug

and add ``'django_extensions'`` to your ``INSTALLED_APPS`` setting in the
``local_settings.py``.

Now you can use ``python -m serveradmin runserver_plus`` to start the local
test webserver with the Werkzeug debugger.

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
   ``__main__.py`` form a project. The "serveradmin" is a project.

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

We will use ``python -m serveradmin`` to create our application::

   python -m serveradmin startapp secinfo

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
