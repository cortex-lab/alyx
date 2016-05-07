Introduction
================================

This document outlines a proposal to improve on the NWB 1.0 format, by adding features that will help lead to more widespread adoption. Specifically, the proposed format addresses the following:

* **Searchability**. To use data, one has to first find the data. The proposed format would allow a user to quickly and simply search a worldwide database of neurophysiology experiments to find that needed for their scientific question. The search could run over all data collected in the user’s own lab, or all the shared data in the world.

* **Lightweight organization.** A barrier to use of the current NWB format is its monolithic nature: in order use a dataset, a user must download the entire file, even if they only need a small part of it. The large size of these files presents a serious barrier to many users.

* **Ease of use.** The HDF5 format at the base of the current NWB format is an obstacle to its adoption by the neurophysiology community; it will be replaced by simple binary files.

* **Cloud-ready.** As more scientists move to cloud-based computing platforms, it is essential that large data files by quickly readable on these systems. HDF5 presents problems in this regard, that are solved by simple binary files.

* **Encouraging uptake.** Working scientists will only switch from their current file formats if there is a strong incentive to do so. The proposed format comes with a “killer app” (an electronic lab notebook database) that will encourage widespread adoption, and also ensure all metadata is provided by experimenters.
