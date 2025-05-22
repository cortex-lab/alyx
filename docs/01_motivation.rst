Motivation
=====================================

Previous standardisation efforts, as well as current data organisation methods used in laboratories, have several drawbacks. Most recently, the `Neurodata Without Borders`_ project has worked to standardise a format for all experimental neurophysiology data. Alyx builds on this work and adds a number of key advantages:

.. _Neurodata Without Borders: https://neurodatawithoutborders.github.io/

- **Searchability**: To use data, one has to first find the data. Alyx allows a user to quickly and simply search a database of neurophysiology experiments to find that needed for their scientific question. The search could run over all data collected in the user’s own lab, or all the shared data in the world.

- **Lightweight organization**: A barrier to use of the current NWB format is its monolithic nature: in order use a dataset, a user must download the entire file, even if they only need a small part of it. The large size of these files presents a serious barrier to many users.

- **Ease of use**: The HDF5 format at the base of the current NWB format is an obstacle to its adoption by the neurophysiology community; it will be replaced by simple binary files.

- **Cloud-ready**:  As more scientists move to cloud-based computing platforms, it is essential that large data files by quickly readable on these systems. HDF5 presents problems in this regard, that are solved by simple binary files.

- **Encouraging uptake**: Working scientists will only switch from their current file formats if there is a strong incentive to do so. The proposed format comes with two “killer apps” that will encourage widespread adoption: a REST API to facilitate those building scientific tools in integrating support for Alyx into their applications, and set of online webforms to ensure all manually-entered metadata is provided by experimenters.
