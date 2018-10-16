REST API
========================

Overview
------------------------

The **base URL** is the URL of your Alyx installation, for example at UCL: https://alyx.cortexlab.net

Note that this URL is only accessible from withing UCL.

With REST_, you make an HTTP request to a particular URL, named an **endpoint**, with possibly some parameters, and you obtain a response in JSON_. There are several types of HTTP requests used in Alyx:

GET
  obtain read-only data about an object, or perform a query

POST
  create a new object

PATCH
  update some fields of an object

PUT
  update all fields of an object

Some GET endpoints return a list of objects satisfying to your query, while other endpoints return the detail of a single object.

The `/` endpoint (base URL) returns the list of all available endpoints.

Every object is identified with a unique 128-bit UUID_, representing by a string of 32 hexadecimal digits, like e.g. `6915b95b-c6d4-45a6-80c3-324675723d3e`.

When we say to do a GET request to the `/blah/` endpoint, we mean to perform an HTTP GET request to the url `https://yourbaseurl/blah/`.

With POST, PATCH, and PUT requests, data is passed as key-value pairs in JSON_. For example, doing a POST request to the `/blah/` endpoint with `key1=val1` and `key2=val2` means performing an HTTP POST request to the url `https://yourbaseurl/blah/` with data a string with the `application/json` mime type, and the contents `{"key1": "val1", "key2": "val2"}`.

.. _REST: https://en.wikipedia.org/wiki/Representational_state_transfer
.. _JSON: https://en.wikipedia.org/wiki/JSON
.. _UUID: https://en.wikipedia.org/wiki/Universally_unique_identifier

In practice, a library in your language should provide you with primitives such as `get(url)`, `post(url, key1=val1, ...)`, etc. so you don't need to understand all of the underlying details: just the HTTP request type, the endpoint URL, the fields you need to pass, and the fields that are returned by the endpoint.


Authentication and public endpoints
-------------------------------------

Some endpoints are public, but most of them are only accessible after authentication.

To authenticate, you need to fetch a token with a GET request to `/auth-token`, with your username and password::

    POST /auth-token/ username=myusername password=mypassword

If successful, the endpoint returns a token::

    {"token":"c719825a24d13ddc52969ba240f9ab6353783095"}

Once you have a token, you should pass it as an `Authorization` HTTP header to any request you make::

    'Authorization: Token c719825a24d13ddc52969ba240f9ab6353783095'

Again, an underlying library should abstract these details away for most users.


Users
-------------------------------------

Manage users.

GET requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GET /users
  List all users


Subjects
-------------------------------------

Manage animal colonies.

GET requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GET /subjects
  List all subjects
GET /subjects?alive=True|False
  Filter by alive
GET /subjects?stock=True|False
  Filter by stock
GET /subjects?water_restricted=True|False
  Filter by water_restricted
GET /subjects?responsible_user=<username>
  Filter by responsibler user
GET /subjects/<nickname>
  Get all the details about a given subject


POST/PATCH requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

POST /subjects
  Create a new subject
PATCH /subjects/<nickname>
  Update a subject


Actions
-------------------------------------

Manage experiments, surgeries, and other actions on animals.

GET requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GET /sessions
  List all sessions
GET /sessions?subject=<nickname>
  Filter by session subject
GET /sessions?start_date|end_date=YYYY-MM-DD
  Filter by start or end date
GET /sessions?starts_before|starts_after|ends_before|ends_after=YYYY-MM-DD
  Filter by start or end date
GET /sessions?dataset_types=dst1,dst2...
  Get all sessions that have datasets of the specified dataset types
GET /sessions/<pk>
  Get the details of a given session

GET /projects
  List all projects
GET /projects/<pk>
  Get the details of a given project


POST/PATCH requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

POST /sessions
  Create a new session
POST /projects
  Create a new project



Water restriction
-------------------------------------

Manage water restriction, water administration, weighings of animals.

GET requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GET /water-administrations
  Get all water administrations
GET /water-administrations/<pk>
  Get the details about a water administration
GET /water-requirement
  Get all water requirements
GET /water-requirement/<pk>
  Get the details about a water requirement
GET /weighings
  Get all weighings
GET /weighings/<pk>
  Get the details about a weighing


POST/PATCH requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

POST /water-administrations
  Create a water administration
POST /weighings
  Create a weighing


Data
-------------------------------------

Manage datasets.

GET requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GET /projects
  Get the list of all projects
GET /projects/<pk>
  Get the details about a project

GET /dataset-types
  Get the list of all dataset types
GET /dataset-types/<pk>
  Get the details about a dataset type

GET /data-formats
  Get the list of all data formats
GET /data-formats/<pk>
  Get the details about a data format

GET /datasets
  Get the list of all datasets
GET /datasets/<pk>
  Get the details about a dataset
GET /datasets?created_datetime_gte=YYYY-MM-DD
  Filter by start or end date
GET /datasets?created_datetime_lte=YYYY-MM-DD
  Filter by start or end date
  example: GET /datasets?created_by=Hamish&dataset_type=Block&created_datetime_lte=2018-01-01

GET /data-repository-type
  Get the list of all data repository types
GET /data-repository-type/<pk>
  Get the details about a data repository type

GET /data-repository
  Get the list of all data repositories
GET /data-repository/<pk>
  Get the details about a data repository

GET /files
  Get the list of all file records
GET /files/<pk>
  Get the details about a file record



POST/PATCH requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

POST /register-file
  Register a bunch of files from a given directory in an existing DataRepository, with the following fields:

  - path=/<nickname>/<YYYY-MM-DD>/<number>/...
  - hostname=<datarepo.dns.com>
  - created_by=<username>
  - filenames=file1.ext1,file2.ext2...
  - projects=proj1,proj2...
