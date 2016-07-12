API specification
========================

This page describes the structure of the Alyx v1 API. While Alyx is still under development, this is liable to change.

Versioning
------------------------

All requests receive the v1 version of the API. For forwards-compatibility, we encourage you to explicitly request this version via the Accept header::

	Accept: application/vnd.alyx.v1+json

Schema
------------------------

All API access should take place over HTTPS; all data is sent and received as JSON::

	curl -i http://alyx.cortexlab.net/
	HTTP/1.1 200 OK
	Date: Tue, 12 Jul 2016 12:58:38 GMT
	Server: Apache/2.4.7 (Ubuntu)
	Vary: Accept,Cookie
	Allow: GET, OPTIONS
	X-Frame-Options: SAMEORIGIN
	Transfer-Encoding: chunked
	Content-Type: application/json

Blank fields are included as null instead of being omitted.

All timestamps are returned in ISO 8601 format::

	YYYY-MM-DDTHH:MM:SSZ

Authentication and public endpoints
-------------------------------------

By default, all endpoints (except for a summary representation of users and their subjects) are only accessible after authentication.

To authenticate, you need to fetch a token. By default, these expire after 24 hours. ::

	curl -X POST -F 'username=foo' -F 'password=bar' https://alyx.cortexlab.net/auth-token/
	{"token":"c719825a24d13ddc52969ba240f9ab6353783095"}

Once you have a token, you should pass it as an `Authorization` header to any request you make::

	curl -X GET http://alyx.cortexlab.net/subjects/ -H 'Authorization: Token c719825a24d13ddc52969ba240f9ab6353783095'

If you pass the wrong credentials, the API will return an error::

	curl -X POST -F 'username=foo' -F 'password=wrong' https://alyx.cortexlab.net/auth-token/
	{"non_field_errors":["Unable to log in with provided credentials."]}

Similarly, if the token has expired or is invalid::

	curl -X GET http://alyx.cortexlab.net/subjects/ -H 'Authorization: Token 123456789abc'
	{"detail":"Invalid token."}

Root endpoint
-------------------------------------

You can issue a GET request to the root endpoint to get all the endpoint categories that the API supports.

	curl https://alyx.cortexlab.net


Summary vs detailed representations
-------------------------------------

When you fetch a list of items, the response may include a subset of the attributes for that resource for performance or bandwidth reasons. This is the "summary" representation of the resource. However, when you fetch an individual item, the full record is returned.

For example, here we fetch a summary representation of all subjects::

	GET /subjects

And now, we request the detailed representation of one specific subject::

	GET /subjects/EJ010

Parameters
--------------------------------------

Many API methods take optional parameters. For GET requests, any parameters not specified as a segment in the path can be passed as an HTTP query string parameter::

	curl -i "https://alyx.cortexlab.net/users/thomas/actions?type=experiment"

In this example, the ``:username`` parameter is in the path (with value ``'thomas'``) while ``:type`` is passed in the query string.

For ``POST``, ``PATCH``, ``PUT``, and ``DELETE`` requests, parameters not included in the URL should be encoded as JSON with a ``Content-Type`` of ``'application/json'``.

Hypermedia and URL cross-links
--------------------------------------

All resources may have one or more ``*_url`` properties linking to other resources. These provide explicit URLs so that proper API clients don't need to construct URLs on their own. It is highly recommended that API clients use these. Doing so will make future upgrades of the API easier for developers. All URLs are expected to be proper `RFC 6570`_ URI templates.

.. _RFC 6570: https://tools.ietf.org/html/rfc6570


