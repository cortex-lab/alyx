Alyx
=================================

Alyx is a database designed for storage and retrieval of all data in an experimental neuroscience laboratory - from subject management through data acquisition, raw data file tracking and storage of metadata resulting from manual analysis.

Alyx is currently used in production at the `Cortexlab at UCL <https://www.ucl.ac.uk/cortexlab>`_ and at the `International Brain Lab <https://www.internationalbrainlab.org>`_.
You can see a live example of it on the `public IBL database <https://openalyx.internationalbrainlab.org>`, (intbrainlab/international).

Alyx is built using industry-standard tools (PostgreSQL_ and Django_) and designed to be interacted with using online webforms to enter and retrieve data manually, or with a documented REST API programmatically (using built-in functions in MATLAB_, Python_, and most other modern programming languages, or command-line tools such as curl_).

It  can be hosted on your own internal server or as a web app in the cloud, for example with Amazon AWS or Microsoft Azure.

.. _PostgreSQL: https://www.postgresql.org/
.. _Django: https://www.djangoproject.com/
.. _Python: https://www.python.org/
.. _MATLAB: http://uk.mathworks.com/products/matlab/
.. _curl: https://curl.haxx.se/

Table of contents:
==================

.. toctree::
   :maxdepth: 2

   gettingstarted.md
   webserving.md
   motivation.rst
   considerations.rst
   api.rst
   models.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
