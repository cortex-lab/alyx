Subjects API
------------------------

List all subjects
========================

Returns list of subjects in summary representation. By default, this will only return currently alive subjects belonging to the current logged-in user. Set ``?alive=all&user=all`` to see all subjects. ::

    GET /subjects

Response:

.. code-block:: json

    [
        {
            "nickname": "CBGADCre1",
            "id": "ac6cfdad-e771-4222-9132-659d972a79dd",
            "responsible_user": "chris",
            "sex": "F",
            "birth_date": "2016-06-12",
            "death_date": null,
            "notes": "",
            "species": "Mus musculus",
            "litter": null,
            "strain": "C57BL/6J",
            "source": "SupplierACME",
            "cage": "Cage4010",
        },
        {
            "nickname": "M141010_CBECB",
            "id": "6a21e543-9f00-4fd2-ac0c-f1dd60830c1f",
            "responsible_user": "thomas",
            "sex": "U",
            "birth_date": null,
            "death_date": null,
            "notes": null,
            "species": null,
            "litter": null,
            "strain": null,
            "source": null,
            "cage": null,
        },
    ]

Parameters
************************

========  ============  ==============
 Name     Type            Description
========  ============  ==============
alive     string         Can be one of ``dead`` or ``alive`` or ``all``. **Default**: ``alive``
username  string         Defaults to showing subjects for logged-in user. Specify this parameter to show a specific user's subjects, or ``all`` to show all users.
========  ============  ==============

Get a specific subject
========================

Returns specific subject in detailed representation. ::

    GET /subjects/CBGADCre1

Response:

.. code-block:: json

    [
        {
            "nickname": "CBGADCre1",
            "id": "ac6cfdad-e771-4222-9132-659d972a79dd",
            "responsible_user": "chris",
            "sex": "F",
            "birth_date": "2016-06-12",
            "death_date": null,
            "notes": "",
            "species": "Mus musculus",
            "litter": null,
            "strain": "C57BL/6J",
            "source": "SupplierACME",
            "cage": "Cage4010",
            "genotype": [
                {
                    "name": "Pvalb-Cre",
                    "zygosity": "Heterozygous"
                },
                {
                    "name": "Piezo2-cKO",
                    "zygosity": "Homozygous"
                }
            ],
            "actions_url": "https://alyx.cortexlab.net/CBGADCre1/actions",
            "datasets_url": "https://alyx.cortexlab.net/CBGADCre1/datasets"
        }
    ]

List all actions for a subject
==================================================

Returns a list of actions performed on a subject, in summary representation. ::

    GET /subjects/CBGADCre1/actions

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


List all datasets for a subject
==================================================

This will list all the URLs of datasets acquired for a particular subject

By default, the summary representation is displayed. However, the ``'detailed'`` representation can be requested; this saves time compared with listing all experiments and manually requesting the API to get all files multiple times. ::

    GET /subjects/CBGADCre1/datasets

Response:

.. code-block:: json

    [
        {
            "id": "660fd619-561c-416a-b528-7b0291d25378",
            "url": "https://alyx.cortexlab.net/datasets/660fd619-561c-416a-b528-7b0291d25378",
            "created_time": "2016-05-12T14:45:01Z",
            "modified_time": "2016-05-12T14:45:01Z",
            "md5": "qwertyu9wef0n",
            "filename": "my_imaging_a1345.tiff",
            "tags": [
                "uncompressed"
            ],
        },
        {
            "id": "110fd619-561c-416a-b528-7b0291d25123",
            "url": "https://alyx.cortexlab.net/datasets/110fd619-561c-416a-b528-7b0291d25123",
            "created_time": "2015-05-12T14:45:01Z",
            "modified_time": "2015-05-12T14:45:01Z",
            "md5": "a9wfnap9w4fn2pfnoi",
            "filename": "my_imaging_aabcc1.tiff",
            "tags": [],
        }
    ]

==============  ============  ==============
 Name           Type            Description
==============  ============  ==============
representation  string         Defaults to ``'summary'``. Setting this to ``detailed`` fetches all filepaths, but will be slower.
==============  ============  ==============

