from django.db import models
from django.utils import timezone

from actions.models import Session
from alyx.base import BaseModel
from misc.models import OrderedUser


def _related_string(field):
    return "%(app_label)s_%(class)s_" + field + "_related"


def _get_or_create_session(subject=None, date=None, number=None, user=None):
    # https://github.com/cortex-lab/alyx/issues/408
    if not subject or not date:
        return None
    # If a base session for that subject and date already exists, use it;
    base = Session.objects.filter(
        subject=subject, start_time__date=date, parent_session__isnull=True).first()
    # otherwise create a base session for that subject and date.
    if not base:
        base = Session.objects.create(
            subject=subject, start_time=date, type='Base', narrative="auto-generated session")
        if user:
            base.users.add(user.pk)
            base.save()
    # If a subsession for that subject, date, and expNum already exists, use it;
    session = Session.objects.filter(
        subject=subject, start_time__date=date, number=number).first()
    # otherwise create the subsession.
    if not session:
        session = Session.objects.create(
            subject=subject, start_time=date, number=number,
            type='Experiment', narrative="auto-generated session")
        if user:
            session.users.add(user.pk)
            session.save()
    # Attach the subsession to the base session if not already attached.
    if not session.parent_session:
        session.parent_session = base
        session.save()
    return session


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

    Stores an absolute path to the repository root as a URI (e.g. for SMB
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
    globus_endpoint_id = models.UUIDField(
        blank=True, null=True, help_text="UUID of the globus endpoint")
    globus_is_personal = models.NullBooleanField(
        blank=True, help_text="whether the Globus endpoint is personal or not. "
        "By default, Globus cannot transfer a file between two personal endpoints.")

    def __str__(self):
        return "<DataRepository '%s'>" % self.name

    class Meta:
        verbose_name_plural = "data repositories"


# Datasets
# ------------------------------------------------------------------------------------------------

class DataFormat(BaseModel):
    """
    A descriptor to accompany a Dataset or DataCollection, saying what sort of information is
    contained in it. E.g. "Neuropixels raw data, formatted as flat binary file" "eye camera
    movie as mj2", etc. Normally each DatasetType will correspond to a specific 3-part alf name
    (for individual files) or the first word of the alf names (for DataCollections)
    """

    name = models.CharField(
        max_length=255, unique=True, blank=True,
        help_text="short identifying nickname, e..g 'npy'.")

    description = models.CharField(
        max_length=255, unique=True, blank=True,
        help_text="Human-readable description of the file format e.g. 'npy-formatted square "
        "numerical array'.")

    alf_filename = models.CharField(
        max_length=255, unique=True, blank=True,
        help_text="string (with wildcards) identifying these files, e.g. '*.*.npy'.")

    matlab_loader_function = models.CharField(
        max_length=255, unique=True, blank=True,
        help_text="Name of MATLAB loader function'.")

    python_loader_function = models.CharField(
        max_length=255, unique=True, blank=True,
        help_text="Name of Python loader function'.")

    class Meta:
        verbose_name_plural = "data formats"

    def __str__(self):
        return "<DataFormat '%s'>" % self.name


class DatasetType(BaseModel):
    """
    A descriptor to accompany a Dataset or DataCollection, saying what sort of information is
    contained in it. E.g. "Neuropixels raw data, formatted as flat binary file" "eye camera
    movie as mj2", etc. Normally each DatasetType will correspond to a specific 3-part alf name
    (for individual files) or the first word of the alf names (for DataCollections)
    """

    name = models.CharField(max_length=255, unique=True,
                            blank=True, help_text="Short identifying nickname, e.g. 'spikes'")

    parent_dataset_type = models.ForeignKey(
        'data.DatasetType', null=True, blank=True,
        help_text="hierachical parent of this DatasetType.")

    created_by = models.ForeignKey(
        OrderedUser, blank=True, null=True,
        related_name=_related_string('created_by'),
        help_text="The creator of the data.")

    description = models.CharField(
        max_length=1023, blank=True,
        help_text="Human-readable description of data type. Should say what is in the file, and "
        "how to read it. For DataCollections, it should list what Datasets are expected in the "
        "the collection. E.g. 'Files related to spike events, including spikes.times.npy, "
        "spikes.clusters.npy, spikes.amps.npy, spikes.depths.npy")

    alf_filename = models.CharField(
        max_length=255, unique=True, blank=True, null=True,
        help_text="File name pattern (with wildcards) for this file in ALF naming convention. "
        "E.g. 'spikes.times.*' or '*.timestamps.*', or 'spikes.*.*' for a DataCollection, which "
        "would include all files starting with the word 'spikes'.")

    def __str__(self):
        return "<DatasetType %s>" % self.name


class BaseExperimentalData(BaseModel):
    """
    Abstract base class for all data acquisition models. Never used directly.

    Contains an Session link, to provide information about who did the experiment etc. Note that
    sessions can be organized hierarchically, and this can point to any level of the hierarchy
    """
    session = models.ForeignKey(
        Session, blank=True, null=True,
        related_name=_related_string('session'),
        help_text="The Session to which this data belongs")

    created_by = models.ForeignKey(
        OrderedUser, blank=True, null=True,
        related_name=_related_string('created_by'),
        help_text="The creator of the data.")

    created_datetime = models.DateTimeField(
        blank=True, null=True, default=timezone.now,
        help_text="The creation datetime.")

    generating_software = models.CharField(
        max_length=255, blank=True,
        help_text="e.g. 'ChoiceWorld 0.8.3'")

    provenance_directory = models.ForeignKey(
        'data.Dataset', blank=True, null=True,
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

    Also note that a Datasets can be hierarchically organized, in which case the parent Datasets
    won't have files directly associated with them.
    """
    name = models.CharField(max_length=255, blank=True)

    md5 = models.UUIDField(blank=True, null=True,
                           help_text="MD5 hash of the data buffer")

    dataset_type = models.ForeignKey(DatasetType, null=True, blank=True)

    data_format = models.ForeignKey(DataFormat, null=True, blank=True)

    parent_dataset = models.ForeignKey(
        'data.Dataset', null=True, blank=True, help_text="hierachical parent of this Dataset.",
        related_name='child_dataset')

    timescale = models.ForeignKey(
        'data.Timescale', null=True, blank=True,
        help_text="Associated time scale (for time series datasets only).")

    def __str__(self):
        return "<Dataset '%s'>" % self.name


# Files
# ------------------------------------------------------------------------------------------------

class FileRecord(BaseModel):
    """
    A single file on disk or tape. Normally specified by a path within an archive. If required,
    more details can be in the JSON
    """
    dataset = models.ForeignKey(Dataset, related_name='file_records')
    data_repository = models.ForeignKey('DataRepository', blank=True, null=True)
    relative_path = models.CharField(
        max_length=1000, blank=True,
        help_text="path name within repository")
    exists = models.BooleanField(
        default=False, help_text="Whether the file exists in the data repository", )

    def __str__(self):
        return "<FileRecord '%s'>" % self.relative_path


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
