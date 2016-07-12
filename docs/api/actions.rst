Actions API
------------------------

List all actions
========================

Returns all actions in summary representation. By default, this will only return actions by currently alive subjects belonging to the current logged-in user. Set ``?alive=all&user=all`` to see all subjects. ::

    GET /actions

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

========  ============  ==============
 Name     Type            Description
========  ============  ==============
type      string         Defaults to ``all``. Can be ``experiment``, ``surgery``, ``virus_injection``, ``note``, or any other Action.
subject   string         Defaults to showing subjects belonging to the logged-in user. Specify this parameter to show a specific subject, or ``all`` to show all subjects.
========  ============  ==============

Get a specific action
========================

Returns the detailed view of a specific action. ::

    GET /actions/660fd619-561c-416a-b528-7b0291d25378

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
    ]
