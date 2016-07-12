Alyx
=================================

Alyx is a fast, flexible database designed for easy storage and retrieval of all data in an experimental neuroscience laboratory - from subject management through data acquisition, raw data file tracking and storage of metadata resulting from manual analysis.

Alyx is built using industry-standard tools (PostgreSQL_ 9.5 and Django_ 1.9) and designed to be interacted with using online webforms to enter and retrieve data manually, or with a documented and easy-to-use REST API programmatically (using built-in functions in MATLAB_, Python_, and most other modern programming languages, or command-line tools such as curl_). It is easy to integrate with existing applications and allows for powerful queries to be performed to filter and return a specific subset of records in milliseconds. It requires minimal setup and can be hosted on your own internal server or in the cloud, for example with Amazon EC2.

.. _PostgreSQL: https://www.postgresql.org/
.. _Django: https://www.djangoproject.com/
.. _Python: https://www.python.org/
.. _MATLAB: http://uk.mathworks.com/products/matlab/
.. _curl: https://curl.haxx.se/

Table of contents:

.. toctree::
   :maxdepth: 2

   motivation.rst
   considerations.rst
   api.rst
   api/users.rst
   api/subjects.rst
   api/actions.rst
   api/datasets.rst
   models.rst


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`