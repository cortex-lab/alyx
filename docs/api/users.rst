Users API
------------------------

Many of the resources on the users API provide a shortcut for getting information about the currently authenticated user. If a request URL does not include a ``:username`` parameter then the response will be for the logged in user.

Get all users
========================

Returns list of users in summary representation. By default, this API is publicly accessible, to help automated login forms. ::

    GET /users

Response:

.. code-block:: json

    [
        {
            "username": "thomas",
            "url": "https://alyx.cortexlab.net/subjects/thomas",
            "subjects_responsible": []
        },
        {
            "username": "chris",
            "url": "https://alyx.cortexlab.net/subjects/chris",
            "subjects_responsible":
            [
                "CMSubj104",
                "CMSubj105"
            ]
        }
    ]

Get a specific user
========================

Returns specific user in detailed representation. ::

    GET /users/:username

Response:

.. code-block:: json

    {
        "id": 4,
        "username": "chris",
        "first_name": "Chris",
        "last_name": "Burgess",
        "subjects_responsible": [
            "CMSubj104",
            "CMSubj105"
        ],
        "actions_url": "https://alyx.cortexlab.net/users/chris/actions",
        "email": "chris@cortexlab.net",
        "created_at": "2010-02-16T01:33:35Z",
        "updated_at": "2010-02-16T01:33:35Z",
    }

List all actions for a user
=================================================


Returns a list of actions performed by a user, in summary representation. ::

    GET /users/chris/actions

Response:

.. code-block:: json

    [
        {
            "type": "surgery",
            "id": "660fd619-561c-416a-b528-7b0291d25378",
            "subject": "CBGADCre01",
            "url": "https://alyx.cortexlab.net/actions/660fd619-561c-416a-b528-7b0291d25378",
            "start_date_time": "2016-05-12T14:45:01Z",
            "end_date_time": "2016-07-12T14:45:36Z",
            "tags": [
                "surgeon training",
                "3D printed implant"
            ],
            "location": "Room 120",
            "users": [
                "chris",
                "thomas"
            ],
            "procedures": [
                "Headplate",
                "Craniotomy"
            ]
        }
        {
            "type": "experiment",
            "id": "134fd619-561c-416a-b528-7b0291d2541b",
            "subject": "CBGADCre01",
            "url": "https://alyx.cortexlab.net/actions/134fd619-561c-416a-b528-7b0291d2541b",
            "start_date_time": "2016-03-12T14:45:10Z",
            "end_date_time": "2016-05-12T14:46:30Z",
            "tags": [
                "headfixed",
                "training session"
            ],
            "location": "BigRig",
            "users": [
                "chris"
            ],
            "procedures": []
        }
    ]

Parameters
************************

========  ============  ==============
 Name     Type            Description
========  ============  ==============
type      string         Defaults to ``all``. Can be ``experiment``, ``surgery``, ``virus_injection``, ``note``, or any other Action.
========  ============  ==============

