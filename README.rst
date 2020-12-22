trac-to-github
==============

Hacks used to migrate from Trac sqlite to GitHub.

Works with Python 3.8.

For wiki migration, you will need git available in your dev environment.

Create a virtualenv::

    virtualenv build
    . build/bin/activate
    mv config.py.sample config.py


For wiki migration::

    python wiki-migrate.py PATH/TO/Trac.DB PATH/TO/GIT-REPO

You might want to add a `_Sidebar.rst` file in the root wit::

    * `<Administrative>`_
    * `<Development>`_
    * `<Infrastructure>`_
    * `<Support>`_
