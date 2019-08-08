Serveradmin: The Machine Readable CMDB
======================================

Serveradmins goal is to be a configuration management database, that's easy to
read from and write to for both humans as well as computers.  The project is
split in two parts.  Serveradmin, the application server component and adminapi,
the python client library.  Humans interact with serveradmin via either
servershell, a webinterface provided by the application server, or via a small
adminapi CLI tool.  We also use a Puppet and a PHP client libraries which don't
life in this repository.

- HA setup
- servershell
- admin interface
    - attribute types
- dajango signals
- python adminapi
- puppet adminapi


.. toctree::
   :maxdepth: 0
   :hidden:

   Introduction<self>


.. toctree::
   :caption: Installation
   :maxdepth: 2
   :hidden:

   Installation<installation/installation>
   Configuration<installation/configuration>


.. toctree::
   :caption: Administration
   :maxdepth: 2
   :hidden:

   Overview<administration/overview>
   Schema<administration/schema>
   Permissions<administration/permissions>
   Graphite<administration/graphite>

.. toctree::
   :caption: API
   :maxdepth: 2
   :hidden:

   Overview<api/overview>
   Authentication<api/authentication>
   Examples<api/examples>

.. toctree::
   :caption: Adminapi
   :maxdepth: 2
   :hidden:

   Overview<adminapi/overview>
   CLI<adminapi/cli>
   Python Library<adminapi/python-library>


.. toctree::
   :caption: Integrations
   :maxdepth: 2
   :hidden:

   PowerDNS<integrations/powerdns>
   Puppet<integrations/puppet>
   Loadbalancer<integrations/loadbalancer>


.. toctree::
   :caption: Development
   :maxdepth: 2
   :hidden:

   Getting Started<development/overview>
   Style Guide<development/style-guide>
   Release Process<development/release>
   New Django App<development/django-app>


