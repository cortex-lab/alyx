Design considerations
=====================================

Metadata vs bulk data
------------------------------------
The data accompanying a neurophysiology experiment has two components: **metadata**, which has complex relational organization but small size; and **bulk data**, which consists of large numerical arrays. While the boundary between metadata and bulk data is not always clear, here we use a simple definition: *metadata is any data that a user will want to search over*. Details of an experiment, and summary statistics of the recorded neurons would be searchable metadata: for example, a user could search for all electrophysiological recordings made in hippocampal area CA1 during linear-track running that contain at least 20 well-isolated narrow-spiking units. However the precise spike times and extracellular waveforms of each unit would be unsearchable bulk data.

Storage of complex relational data, and storage of large numerical arrays are both solved problems in computing. We apply tried-and-tested solutions:

* Metadata is stored in an SQL database. A web interface allows users to update this metadata quickly and easily, for example while doing an experiment.
* Bulk data is stored with one binary file per numerical array, and the URI (i.e. location) of each file stored in the SQL database. The Open Neurophysiology Environment (ONE) interface allows users to search and access this bulk data.

Unstructured and arbitrary metadata
------------------------------------
It is impossible to predict the metadata users will want to store for their experiments, as experimental paradigms are constantly evolving. Traditional relational databases, however, require all columns to be defined ahead of time. We will solve this problem by giving each table an additional “json” column that contains a JSON-formatted string, which can easily be converted into a MATLAB struct. PostgreSQL allows such fields to be searched in a similar way to traditional columns.

Unique identifiers
------------------------------------
Databases identify each entry in a table with a “primary key”. As primary keys, we give each entry in a table (e.g. a subject, a lab, an experiment, or a neuron) a “GUID” – a random 128-bit number – which makes the chance of key duplication vanishingly small, even if this schema were used to store all the world’s neuroscience data. This GUID is assigned when the item is first added to the database (e.g. when a web form is filled in for an experiment; after spike sorting; etc.). The use of GUIDs allows users to copy or transfer their data to centralized stores with negligible danger of ID clash.

API and webform access
------------------------------------
All database tables described in :doc:`the Models page </models>` are accessible by a series of online webforms; each webform broadly represents one table. A subset of data, described in :doc:`the API documentation </api>`, are accessible programmatically via an online HTTP REST API; these are 'serialized' to avoid users having to write their own database joins and views as much as possible.

Initially, only the data which is likely to be accessed programmatically is made accessible via the API; subjects, experiments, data and analyis results are all exposed in the API, but information about the lab or editing detailed user permissions information is not.

Sharing
------------------------------------
This system was originally designed to be used within a single lab, as an “electronic lab notebook” that keeps track of the experiments performed and datasets produced. It can also be used by multi-lab collaborations, and is now used for data management by the International Brain Lab. 
