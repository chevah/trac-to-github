trac-to-github
==============

Hacks used to migrate from Trac sqlite to GitHub.

Works with Python 3.8.

For wiki migration, you will need git available in your dev environment.

Create a virtualenv::

    virtualenv build
    . build/bin/activate
    mv config.py.sample config.py


For wiki migration.
All pages are generated into a flat file structure.
Spaces are used instead of path separators::

    python wiki_migrate.py PATH/TO/Trac.DB PATH/TO/GIT-REPO

You might want to add a `_Sidebar.rst` file in the root with::

    * `<Administrative>`_
    * `<Development>`_
    * `<Infrastructure>`_

      * `Services <Infrastructure-Services>`_
      * `Machines <Infrastructure-Machines>`_

    * `<Support>`_

For wiki content conversion::

    python wiki_trac_rst_convert.py PATH/TO/GIT-REPO


Things that are not yet auto-converted:

* TracWiki 3rd level heading `=== Some sub-section ===`
* Sub-pages listing macro `[[TitleIndex(Development/)]]`
* Local table of content `[[PageOutline]]`
* Manually create _Sidebar.rst and _Footer.rst GitHub wiki meta-pages.
