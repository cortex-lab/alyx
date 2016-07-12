Datasets API
------------------------

List all datasets
========================

Returns list of datasets in summary representation ::

    GET /datasets

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

Get a specific dataset
========================

Returns specific subject in detailed representation. ::

    GET /datasets/660fd619-561c-416a-b528-7b0291d25378

Response:

.. code-block:: json

    [
        {
            "id": "660fd619-561c-416a-b528-7b0291d25378",
            "url": "https://alyx.cortexlab.net/datasets/660fd619-561c-416a-b528-7b0291d25378",
            "created_time": "2016-05-12T14:45:01Z",
            "modified_time": "2016-05-12T14:45:01Z",
            "md5": "2016-05-12T14:45:01Z",
            "filename": "my_imaging_a1345.tiff",
            "filepaths": [
                {
                    "type": "local",
                    "hostname": "chris_pc",
                    "path": "C:/DATA/CBGADCre1/2016-05-12/2photon/my_imaging_a1345.tiff",
                },
                {
                    "type": "smb",
                    "path": "\\dataserver.cortexlab.net\subjects\CBGADCre1\2016-05-12\2photon\my_imaging_a1345.tiff",
                },
                {
                    "type": "tape_archive",
                    "id": "CL0005",
                }
            ],
            "tags": [
                "uncompressed"
            ],
        }
    ]

