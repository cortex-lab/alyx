General considerations
=====================================

Before describing the tables in the proposed database, we outline some general design considerations.

Unique identifiers
----------------------
Databases identify each entry in a table with a “primary key”. As primary keys, we will give each entry in a table (e.g. a subject, a lab, an experiment, or a neuron) a “GUID” – a random 128-bit number – which makes the chance of key duplication vanishingly small, even if this schema were used to store all the world’s neuroscience data. This GUID is assigned when the item is first added to the database (e.g. when a web form is filled in for an experiment; after spike sorting; etc.). The use of GUIDs will allow users to copy or transfer their data to centralized stores without danger of ID clash.

Ad-hoc columns
----------------------
It is impossible to predict the metadata users will want to store for their experiments, as experimental paradigms are constantly evolving. Traditional relational databases, however, require all columns to be defined ahead of time. We will solve this problem by giving each table an additional “user_data” column that contains a JSON-formatted string. Modern relational database systems such as PostgreSQL allow such fields to be searched as easily as traditional columns.

Controlled-vocabulary text fields
-----------------------------------
Many fields in the schema allow one of a small list of options. For example when describing a sex, one almost always selects “male”, or “female”.  To allow extensibility to unforeseen situations, you can also enter a different value if you have to (e.g. “unknown”). This situation is denoted by listing the standard options in angle brackets: <male, female>.
