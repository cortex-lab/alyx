from django.db import models
from django.contrib.postgres.fields import ArrayField

from actions.models import Session
from alyx.base import BaseModel


###############################################################################
# Data repositories (local, server, archive). All information is in JSON and type
###############################################################################

class RepositoryType(BaseModel):
    name = models.CharField(max_length=255)


class DataRepository(BaseModel):
    """
    Base class for a file storage device; this could be a local hard-drive on a laptop,
    a network file location, or an offline archive tape / Blu-Ray disc / hard-drive.
	
	Information about the repository is stored in JSON in a type-specific manner
    """
    name = models.CharField(max_length=255)
    repository_type = models.ForeignKey(RepositoryType, null=True, blank=True)

    def get_valid_name(session_id=None):
        """TODO: Returns a default filepath for a new session. session_id
        must exist and be linked to a valid Subject."""
        pass

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "data repositories"


###############################################################################
# Files 
###############################################################################

class FileRecord(BaseModel):
    """
    A single file on disk or tape. Normally specified by a path within an archive. In some
    cases (like for a single array split over multiple binary files) more details can be in
    the JSON
    """

    dataset_id = models.ForeignKey('Dataset', related_name='file_records')
    path = models.CharField(
        max_length=1000, help_text="path name within repository")
    data_repository_id = models.ForeignKey('DataRepository')

    def __str__(self):
        return self.filename
		
class BaseExperimentalData(BaseModel)
    """
    Abstract base class for all data acquisition models. Never used directly.
	
	Contains a session_id link, which will provide information about who did the experiment etc.
	Information about experiment #, series, etc. can go in the JSON
    """
    session_id = models.ForeignKey(Session, related_name="%(app_label)s_%(class)s_related",
                                help_text="The Session to which this data belongs")

    class Meta:
        abstract = True

class Dataset(BaseExperimentalData)
    """
    A chunk of data that is stored outside the database, most often a rectangular binary array.
    There can be multiple FileRecords for one Dataset, if it is stored multiple places,
    which can have different types depending on how the file is stored

    Note that by convention, binary arrays are stored as .npy and text arrays as .tsv
    """
    name = models.CharField(max_length=255, blank=True)

    # KDH: since most Datasets belong to Experimental data types, might this be redundant
    # with the session link in BaseExperimentalData ?
    session = models.ForeignKey(Session, null=True, blank=True, help_text="which experimental"
                                "session this dataset is associated with")
	dataset_type_id = models.ForeignKey(DatasetType, null=True, blank=True)

    def __str__(self):
        return str(getattr(self, 'name', 'unnamed'))

class DatasetType(BaseModel)
    """
    A descriptor to accompany a dataset, saying what sort of information is contained in it
	E.g. "Neuropixels raw data" "eye camera movie", etc.
    """

    name = models.CharField(max_length=255, blank=True, help_text="description of data type")

	
###############################################################################
# Time alignment
###############################################################################


class Timescale(BaseModel)
	"""
	A timescale that is used to align recordings on multiple devices. 
	There can be multiple timescales for a single experiment, which could be used for example 
	if some information could only be aligned with poor temporal resolution.
	
	However there can only be one timescale with the flag "final" set to True at any moment. 
	This should reflect a final, accurate time alignement, that can be used by data analysts who 
	do not need to understand how time alignment was performed. It should have a sample rate of 1.
	
	When users search for data, they will normally search for a timescale that is linked to timeseries
	of the appropriate kind.
	"""
	
	name = models.CharField(max_length=255, blank=True, help_text="informal name describing this field")
	nominal_start = models.DateTimeField(help_text="Approximate date and time corresponding to 0 samples")
	nominal_sampling_rate = models.FloatField(help_text="Nominal sampling rate of this timescale (1 for final)"
	final = models.BooleanField(help_text="set to true for the final results of time alignment, in seconds")
	info = models.CharField(max_length=255, blank=True, help_text="any information, e.g. length of break"
								" around 300s inferred approximately from computer clock")
	
	def __str__(self):
        return self.filename
	
	class Meta:
        verbose_name_plural = 'Time scales'
	

class TimeSeries(Dataset):
    """
    A special type of Dataset with associated timestamps, relative to specified timescale.
	
	If a recording has been aligned to more than one Timescale, there will be multiple TimeSeries objects, that 
	with the same primary data file but different timestamp files
    """
    timestamps = models.ForeignKey(Dataset,
                                    related_name='related_time_series_times',
                                    help_text="N*2 array containing sample numbers and their associated timestamps")
	timescale_id = models.ForeignKey(Timescale)

    class Meta:
        verbose_name_plural = 'Time series'

		
class EventSeries(BaseExperimentalData):
    """
    Links to a file containing a set of event times and descriptions,
    such as behavioral events or sensory stimuli.
    """
	timescale_id = models.ForeignKey(Timescale, help_text="which timescale this is on")
    event_times = models.ForeignKey(Dataset, blank=True, null=True,
                                    related_name="event_series_event_times",
                                    help_text="n*1 array of times")
    event_types_id = models.ForeignKey(Dataset, blank=True, null=True,
                                       related_name="event_series_event_descriptions",
                                       help_text="n*1 array listing the type of each event, numbers or strings")
    type_descriptions_id = models.ForeignKey(Dataset, blank=True, null=True,"nTypes*2 text array (.tsv) describing event types"))
    
    description = models.TextField(blank=True,
                                   help_text="misc. narrative e.g. "
                                   "'drifting gratings of different orientations', "
                                   "'ChoiceWorld behavior events'")
    generating_software = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'ChoiceWorld 0.8.3'")
    provenance_directory = models.ForeignKey(Dataset, blank=True, null=True,
                                             related_name="event_series_provenance",
                                             help_text="link to directory containing "
                                             "intermediate results")

    class Meta:
        verbose_name_plural = 'Event series'


class IntervalSeries(BaseExperimentalData):
    """
    Links to a file containing a set of start/end pairs and descriptions,
    such as behavioral intervals or extended sensory stimuli.
    """
	timescale_id = models.ForeignKey(Timescale, help_text="which timescale this is on")
	interval_times = models.ForeignKey(Dataset, blank=True, null=True,
                                       related_name="interval_series_interval_times",
                                       help_text="n*2 array of start and end times")
    interval_types = models.ForeignKey(Dataset, blank=True, null=True,
                                       related_name="interval_series_interval_descriptions",
                                       help_text="n*1 array listing the type of each interval")
    type_descriptions = models.ForeignKey(Dataset, blank=True, null=True)
    description = models.TextField(blank=True,
                                   help_text="misc. narrative e.g. "
                                   "'drifting gratings of different orientations', "
                                   "'ChoiceWorld behavior intervals'")
    generating_software = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'ChoiceWorld 0.8.3'")
    provenance_directory = models.ForeignKey(Dataset, blank=True, null=True,
                                             related_name="interval_series_provenance",
                                             help_text="link to directory containing "
                                             "intermediate results")

    class Meta:
        verbose_name_plural = 'Interval series'