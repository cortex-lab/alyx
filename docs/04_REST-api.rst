REST API
========================

Overview
------------------------

The **base URL** is the URL of your Alyx installation, for example at IBL: https://openalyx.internationalbrainlab.org

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

Going further
------------------------
The list of endpoints, fields and methods is self-documented for each database at the  `/docs` URL.
For example, a public Alyx instance is available here for reference: https://openalyx.internationalbrainlab.org/docs/

REST endpoints are programmatically accessed client side. And example of a client side application is described in details here: [https://one.internationalbrainlab.org/](https://int-brain-lab.github.io/ONE/).
