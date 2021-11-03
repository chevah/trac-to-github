trac-to-github
==============

Hacks used to migrate from Trac sqlite or Postgresql dump to GitHub.

Works with Python 3.8.

# Wiki migration

For wiki migration, you will need git available in your dev environment.

This is a 3 stage process:

1. Copy `config.py.sample` over `config.py`, and edit all the settings.

2. Create the GitHub Wiki pages using content formated as TracWiki.
   This is done to have better diffs between historic versions.

3. Convert the last version of the each page to ReStructuredText,
   or to any other format.


Convert to git repo
===================

Create a virtualenv::

    virtualenv build
    . build/bin/activate
    mv config.py.sample config.py

Modify the config.py values.

All pages are generated into a flat file structure.
Spaces are used instead of path separators::

    python wiki_migrate.py PATH/TO/Trac.db3 PATH/TO/GIT-REPO

You might want to add a `_Sidebar.rst` file in the root with::

    * `<Administrative>`_
    * `<Development>`_
    * `<Infrastructure>`_

      * `Services <Infrastructure-Services>`_
      * `Machines <Infrastructure-Machines>`_

    * `<Support>`_


Convert the content to RST
==========================

For wiki content conversion::

    python wiki_trac_rst_convert.py PATH/TO/GIT-REPO


Things that are not yet auto-converted:

* TracWiki 3rd level heading `=== Some sub-section ===`
* Sub-pages listing macro `[[TitleIndex(Development/)]]`
* Local table of content `[[PageOutline]]`
* Manually create _Sidebar.rst and _Footer.rst GitHub wiki meta-pages.

# Ticket migration

1. Copy `config.py.sample` over `config.py`, and edit all the settings.
2. Get the latest `projects_created.tsv` to avoid duplicating projects.
3. Modify `select_tickets` to your liking.
4. If you are sure you want to create tickets, change `DRY_RUN` to `False`
   in `ticket_migrate.py`.
5. Run `./ticket_migrate.py ../trac.db`, where `../trac.db` is the path
   to the Trac SQLite DB dump.

