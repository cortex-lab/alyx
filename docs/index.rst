Alyx
=================================

Alyx is a database designed for storage and retrieval of all data in an experimental neuroscience laboratory - from subject management through data acquisition, raw data file tracking and storage of metadata resulting from manual analysis.

Alyx is currently used in production at the `Cortexlab at UCL <https://www.ucl.ac.uk/cortexlab>`_ and at the `International Brain Lab <https://www.internationalbrainlab.org>`_.
You can see a live example of it on the `public IBL database <https://openalyx.internationalbrainlab.org>`_ (access: intbrainlab/international).

Alyx is built using industry-standard tools (PostgreSQL_ and Django_) and designed to be interacted with using online webforms to enter and retrieve data manually, or with a documented REST API programmatically. An example of a client side Python tool is ONE_.

Alyx web application can be hosted on your own internal server or as a web app in the cloud, for example with Amazon AWS or Microsoft Azure.

.. _ONE: https://int-brain-lab.github.io/ONE/
.. _PostgreSQL: https://www.postgresql.org/
.. _Django: https://www.djangoproject.com/

Table of contents:
==================

.. toctree::
   :maxdepth: 2

   00_gettingstarted.md
   01_motivation.rst
   03_deployment.md
   04_REST-api.rst
   05_models.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
