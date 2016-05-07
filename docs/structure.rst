General structure
===================

The data accompanying a neurophysiology experiment has two components: **metadata**, which has complex relational organization but small size; and **bulk data**, which consists of large numerical arrays. While the boundary between metadata and bulk data is not always clear, here we use a simple definition: *metadata is any data that a user will want to search over*. Details of an experiment, and summary statistics of the recorded neurons would be searchable metadata: for example, a user could search for all electrophysiological recordings made in hippocampal area CA1 during linear-track running that contain at least 20 well-isolated narrow-spiking units. However the precise spike times and extracellular waveforms of each unit would be unsearchable bulk data.

Storage of complex relational data, and storage of large numerical arrays are both solved problems in computing. We will apply tried-and-tested solutions:

* Metadata will be stored in an SQL database

* Bulk data will be stored with one binary file per numerical array, and the URI (i.e. location) of each file stored in the SQL database.

This system can be used within a lab, as an “electronic lab notebook” that keeps track of the experiments performed and datasets produced within a lab.  We are currently developing such a system for our own lab, based on a set of simple user-friendly webforms that update the database when a scientist performs an action such as a surgery or experiment, or an analysis such as spike sorting. Because many labs urgently need a way to organize their own data, a well-designed, freely available and supported lab database system is likely to see wide use.

This system also makes data sharing straightforward: a lab can share selected datasets by granting access to a portion of their database and bulk data store; and a data user can analyze this data using exactly the same tools they would use to analyze data collected in their own lab. Alternatively, the bulk data files and database entries for a set of completed experiments can uploaded to a centralized store, to ensure long-term archival without requiring continuing support from the originating lab.

The remainder of this document describes in detail a proposed database schema to cover most current neurophysiology experiments, and a proposed organization of the bulk data store to cover most types of data currently collected. This schema is essentially a translation of the NWB 1.0 format into a relational form.
