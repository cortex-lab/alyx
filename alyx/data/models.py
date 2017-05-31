from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from actions.models import Session
from alyx.base import BaseModel


# Data repositories (local, server, archive). All information is in JSON and type
# ------------------------------------------------------------------------------------------------

class DataRepositoryType(BaseModel):
    name = models.CharField(max_length=255)


class DataRepository(BaseModel):
    """
    Base class for a file storage device; this could be a local hard-drive on a laptop,
    a network file location, or an offline archive tape / Blu-Ray disc / hard-drive.

    Information about the repository is stored in JSON in a type-specific manner
    """
    name = models.CharField(max_length=255)
    repository_type = models.ForeignKey(DataRepositoryType, null=True, blank=True)
    path = models.CharField(
        max_length=1000, blank=True,
        help_text="absolute path to the repository")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "data repositories"


# Files
# ------------------------------------------------------------------------------------------------

_related_string = lambda field: "%(app_label)s_%(class)s_" + field + "_related"


class FileRecord(BaseModel):
    """
    A single file on disk or tape. Normally specified by a path within an archive. In some
    cases (like for a single array split over multiple binary files) more details can be in
    the JSON
    """
    dataset = models.ForeignKey('Dataset', related_name=_related_string('dataset'))
    data_repository = models.ForeignKey('DataRepository', blank=True, null=True)
    relative_path = models.CharField(
        max_length=1000, blank=True,
        help_text="path name within repository")

    def __str__(self):
        return self.filename


# Datasets
# ------------------------------------------------------------------------------------------------

class BaseExperimentalData(BaseModel):
    """
    Abstract base class for all data acquisition models. Never used directly.

    Contains a session link, which will provide information about who did the experiment etc.
    Information about experiment #, series, etc. can go in the JSON
    """
    session = models.ForeignKey(
        Session, blank=True, null=True,
        related_name=_related_string('session'),
        help_text="The Session to which this data belongs")
    created_by = models.ForeignKey(
        User, blank=True, null=True,
        related_name=_related_string('created_by'),
        help_text="The creator of the data.")
    created_date = models.DateTimeField(
        blank=True, null=True, default=timezone.now,
        help_text="The creation date.")

    class Meta:
        abstract = True


class DatasetType(BaseModel):
    """
    A descriptor to accompany a dataset, saying what sort of information is contained in it
    E.g. "Neuropixels raw data" "eye camera movie", etc.
    """

    name = models.CharField(max_length=255, blank=True, help_text="description of data type")


class Dataset(BaseExperimentalData):
    """
    A chunk of data that is stored outside the database, most often a rectangular binary array.
    There can be multiple FileRecords for one Dataset, if it is stored multiple places,
    which can have different types depending on how the file is stored

    Note that by convention, binary arrays are stored as .npy and text arrays as .tsv
    """
    name = models.CharField(max_length=255, blank=True)
    md5 = models.UUIDField(blank=True, null=True, help_text="MD5 hash of the data buffer")

    dataset_type = models.ForeignKey(DatasetType, null=True, blank=True)

    def __str__(self):
        return str(getattr(self, 'name', 'unnamed'))


# Time alignment
# ------------------------------------------------------------------------------------------------

class Timescale(BaseExperimentalData):
    """
    A timescale that is used to align recordings on multiple devices.
    There can be multiple timescales for a single experiment, which could be used for example
    if some information could only be aligned with poor temporal resolution.

    However there can only be one timescale with the flag "final" set to True at any moment.
    This should reflect a final, accurate time alignement, that can be used by data analysts who
    do not need to understand how time alignment was performed. It should have a sample rate of 1.

    When users search for data, they will normally search for a timescale that is linked to
    timeseries of the appropriate kind.
    """

    name = models.CharField(
        max_length=255, blank=True,
        help_text="informal name describing this field")

    nominal_start = models.DateTimeField(
        blank=True, null=True,
        help_text="Approximate date and time corresponding to 0 samples")

    nominal_time_unit = models.FloatField(
        blank=True, null=True,
        help_text="Nominal time unit for this timescale (in seconds)")

    final = models.BooleanField(
        help_text="set to true for the final results of time alignment, in seconds")

    info = models.CharField(
        max_length=255, blank=True,
        help_text="any information, e.g. length of break around 300s inferred approximately "
        "from computer clock")

    def __str__(self):
        return self.filename

    class Meta:
        verbose_name_plural = 'Time scales'


class TimeSeries(BaseExperimentalData):
    """
    A special type of Dataset with associated timestamps, relative to specified timescale.

    If a recording has been aligned to more than one Timescale, there will be multiple
    TimeSeries objects, that with the same primary data file but different timestamp files
    """
    data = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('data'),
        help_text="N*2 array containing sample numbers and their associated timestamps")

    timestamps = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('timestamps'),
        help_text="N*2 array containing sample numbers and their associated timestamps")

    timescale = models.ForeignKey(Timescale, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Time series'


class EventSeries(BaseExperimentalData):
    """
    Links to a file containing a set of event times and descriptions,
    such as behavioral events or sensory stimuli.
    """
    timescale = models.ForeignKey(
        Timescale, blank=True, null=True,
        help_text="which timescale this is on")

    event_times = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('event_times'),
        help_text="n*1 array of times")

    event_types = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('event_types'),
        help_text="n*1 array listing the type of each event, numbers or strings")

    type_descriptions = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('type_descriptions'),
        help_text="nTypes*2 text array (.tsv) describing event types")

    description = models.TextField(
        blank=True,
        help_text="misc. narrative e.g. 'drifting gratings of different orientations', "
        "'ChoiceWorld behavior events'")

    generating_software = models.CharField(
        max_length=255, blank=True,
        help_text="e.g. 'ChoiceWorld 0.8.3'")

    provenance_directory = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('provenance'),
        help_text="link to directory containing intermediate results")

    class Meta:
        verbose_name_plural = 'Event series'


class IntervalSeries(BaseExperimentalData):
    """
    Links to a file containing a set of start/end pairs and descriptions,
    such as behavioral intervals or extended sensory stimuli.
    """
    timescale = models.ForeignKey(
        Timescale, blank=True, null=True,
        help_text="which timescale this is on")

    interval_times = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('interval_times'),
        help_text="n*2 array of start and end times")

    interval_types = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('interval_types'),
        help_text="n*1 array listing the type of each interval")

    type_descriptions = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('type_descriptions'),
        help_text="interval series type descriptions")

    description = models.TextField(
        blank=True,
        help_text="misc. narrative e.g. 'drifting gratings of different orientations', "
        "'ChoiceWorld behavior intervals'")

    generating_software = models.CharField(
        max_length=255, blank=True,
        help_text="e.g. 'ChoiceWorld 0.8.3'")

    provenance_directory = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('provenance'),
        help_text="link to directory containing  intermediate results")

    class Meta:
        verbose_name_plural = 'Interval series'
