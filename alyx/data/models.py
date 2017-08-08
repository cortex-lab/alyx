from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from actions.models import Session, Experiment
from alyx.base import BaseModel


def _related_string(field):
    return "%(app_label)s_%(class)s_" + field + "_related"


# Data repositories
# ------------------------------------------------------------------------------------------------

class DataRepositoryType(BaseModel):
    """
    A type of data repository, e.g. local SAMBA file server; web archive; LTO tape
    """
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return "<DataRepositoryType '%s'>" % self.name


class DataRepository(BaseModel):
    """
    A data repository e.g. a particular local drive, specific cloud storage
    location, or a specific tape.

    Stores an absolute path to the repository rootas a URI (e.g. for SMB
    file://myserver.mylab.net/Data/ALF/; for web
    https://www.neurocloud.edu/Data/). Additional information about the
    repository can stored in JSON  in a type-specific manner (e.g. which
    cardboard box to find a tape in)
    """

    name = models.CharField(max_length=255)
    repository_type = models.ForeignKey(
        DataRepositoryType, null=True, blank=True)
    path = models.CharField(
        max_length=1000, blank=True,
        help_text="absolute URI path to the repository")

    def __str__(self):
        return "<DataRepository '%s'>" % self.name

    class Meta:
        verbose_name_plural = "data repositories"


# Datasets
# ------------------------------------------------------------------------------------------------


class DatasetType(BaseModel):
    """
    A descriptor to accompany a dataset, saying what sort of information is contained in it
    E.g. "Neuropixels raw data" "eye camera movie", etc.
    """

    name = models.CharField(max_length=255, unique=True,
                            blank=True, help_text="description of data type")

    def __str__(self):
        return "<DatasetType %s>" % self.name


class BaseExperimentalData(BaseModel):
    """
    Abstract base class for all data acquisition models. Never used directly.

    Contains an Session link, to provide information about who did the experiment etc. and
    also optionally an Experiment link to assign it to a subcomponent of that Session
    """
    session = models.ForeignKey(
        Session, blank=True, null=True,
        related_name=_related_string('session'),
        help_text="The Session to which this data belongs")

    experiment = models.ForeignKey(
        Experiment, blank=True, null=True,
        related_name=_related_string('session'),
        help_text="The Experiment to which this data belongs")

    created_by = models.ForeignKey(
        User, blank=True, null=True,
        related_name=_related_string('created_by'),
        help_text="The creator of the data.")

    created_datetime = models.DateTimeField(
        blank=True, null=True, default=timezone.now,
        help_text="The creation datetime.")

    generating_software = models.CharField(
        max_length=255, blank=True,
        help_text="e.g. 'ChoiceWorld 0.8.3'")

    provenance_directory = models.ForeignKey(
        'Dataset', blank=True, null=True,
        related_name=_related_string('provenance'),
        help_text="link to directory containing intermediate results")

    class Meta:
        abstract = True


class Dataset(BaseExperimentalData):
    """
    A chunk of data that is stored outside the database, most often a rectangular binary array.
    There can be multiple FileRecords for one Dataset, which will be different physical files,
    all containing identical data, with the same MD5.

    Note that by convention, binary arrays are stored as .npy and text arrays as .tsv
    """
    name = models.CharField(max_length=255, blank=True)
    md5 = models.UUIDField(blank=True, null=True,
                           help_text="MD5 hash of the data buffer")

    dataset_type = models.ForeignKey(DatasetType, null=True, blank=True)

    def __str__(self):
        return "<Dataset '%s'>" % self.name


# Files
# ------------------------------------------------------------------------------------------------

class FileRecord(BaseModel):
    """
    A single file on disk or tape. Normally specified by a path within an archive. If required,
    more details can be in the JSON
    """
    dataset = models.ForeignKey('Dataset', related_name=_related_string('dataset'))
    data_repository = models.ForeignKey('DataRepository', blank=True, null=True)
    relative_path = models.CharField(
        max_length=1000, blank=True,
        help_text="path name within repository")

    def __str__(self):
        return "<FileRecord '%s'>" % self.relative_path


# Data collections and time series
# ------------------------------------------------------------------------------------------------

class DataCollection(BaseExperimentalData):
    """
    A collection of datasets that all describe different aspects of the same objects. For example,
    the filtered and unfiltered waveforms of a set of spike clusters. Each file in the collection
    must have the same number of rows (or the same leading dimension for higher-dim arrays). The
    timeseries classes will inherit from this.
    """
    name = models.CharField(
        max_length=255, blank=True,
        help_text="description of the data in this collection (e.g. cluster information)")

    data = models.ManyToManyField(
        Dataset, blank=True, null=True,
        related_name=_related_string('data'),
        help_text="Datasets, each of which  should have their own descriptions and DatasetTypes")

    def __str__(self):
        return "<DataCollection '%s'>" % self.name


class Timescale(BaseModel):
    """
    A timescale that is used to align recordings on multiple devices.
    There could be multiple timescales for a single experiment, which could be used for example
    if some information could only be aligned with poor temporal resolution.

    However there can only be one timescale with the flag "final" set to True at any moment.
    This should reflect a final, accurate time alignement, that can be used by data analysts who
    do not need to understand how time alignment was performed. It should have a sample rate of 1.

    When users search for data, they will normally search for a timescale that is linked to
    timeseries of the appropriate kind.

    A timescale is always associated with a session, and can also optionally be associated with a
    series or experiment.
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
        return "<Timescale '%s'>" % self.name

    class Meta:
        verbose_name_plural = 'Time scales'


class TimeSeries(DataCollection):
    """
    A collection of Datasets that were all sampled together, associated with a single set of
    timestamps, relative to specified timescale. This is a DataCollection together with a
    timescale ID and a timestamps file.

    In principle, you could store multiple TimeSeries with the same data but different
    Timescales.
    To avoid confusing data users, however, this is not recommended - only register the final
    timescale into the database, and don't register intermediate timescales unless there is a
    good reason to.
    """

    timestamps = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('timestamps'),
        help_text="N*2 array containing sample numbers and their timestamps "
        "on associated timescale")

    timescale = models.ForeignKey(
        Timescale, blank=True, null=True,
        help_text="which timescale this is on")

    class Meta:
        verbose_name_plural = 'Time series'


class EventSeries(DataCollection):
    """
    Links to a file containing a set of event times, and other files with further information,
    such as behavioral events or sensory stimuli. This is a DataCollection together with a times
    file and a timestamp ID.
    """

    timescale = models.ForeignKey(
        Timescale, blank=True, null=True,
        help_text="which timescale this is on")

    times = models.ForeignKey(
        'Dataset', blank=True, null=True,
        related_name=_related_string('event_times'),
        help_text="n*1 array of times on specified timescale")

    class Meta:
        verbose_name_plural = 'Event series'


class IntervalSeries(BaseExperimentalData):
    """
    Links to a file containing a set of event times, and other files with further information,
    such as behavioral events or sensory stimuli. This is a DataCollection together with a times
    file and a timestamp ID.
    """
    timescale = models.ForeignKey(
        Timescale, blank=True, null=True,
        help_text="which timescale this is on")

    intervals = models.ForeignKey(
        Dataset, blank=True, null=True,
        related_name=_related_string('interval_times'),
        help_text="n*2 array of start and end times")

    class Meta:
        verbose_name_plural = 'Interval series'
