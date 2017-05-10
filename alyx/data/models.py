from django.db import models
from django.contrib.postgres.fields import ArrayField, JSONField

from actions.models import Session
from alyx.base import BaseModel, BasePolymorphicModel

###############################################################################
# Data repositories (local, server, archive). All information is in JSON and type
###############################################################################

class DataRepository(BaseModel):
    """
    Base class for a file storage device; this could be a local hard-drive on a laptop,
    a network file location, or an offline archive tape / Blu-Ray disc / hard-drive.
    """
    name = models.CharField(max_length=255)
	type = models.CharField(max_length=255, help_text="e.g. web, local_disk, torrent")
	# KDH: assuming JSON is there from BaseModel
    # TODO: type introspection for location type. KDH: no idea what this means!

    def get_valid_name(session_id=None):
        """TODO: Returns a default filepath for a new session. session_id
        must exist and be linked to a valid Subject."""
        pass

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "data repositories"


###############################################################################
# Files and filetypes
###############################################################################

class Dataset(BaseModel):
    """
	A chunk of data that is stored outside the database, most often a rectangular binary array.
	There can be multiple FileRecords for one Dataset, if it is stored multiple places,
	and they can have different types depending on how the file is stored
	"""
    name = models.CharField(max_length=255, blank=True)
	tag = models.CharField(max_length=255, blank=True, help_text="User-defined tag saying"
							"what type of file this is (e.g. which program made it)")
	session = models.ForeignKey(Session, null=True, blank=True, help_text="which experimental"
									"session this dataset is associated with")

    def __str__(self):
        return str(getattr(self, 'name', 'unnamed'))


class FileRecord(BaseModel):
    """
	A single file on disk or tape. Normally specified by a path within an archive. In some 
	cases (like for a single array split over multiple binary files) more details can be in 
	the JSON
	"""

    dataset = models.ForeignKey('Dataset', related_name='file_records')
    path = models.CharField(
        max_length=1000, help_text="path name within repository")
    data_repository = models.ForeignKey('DataRepository')
	
    
	def __str__(self):
        return self.filename

class TimeSeries(Dataset):
	""""
	A special type of Dataset with associated timestamps, relative to a universal timebase in seconds
	""""
    stamp_times = models.ForeignKey(Dataset, help_text="1d array containing times of each timestamp"
	stamp_samples = models.ForeignKey(Dataset, help_text="1d array of integers containing samples"
										" these timestamps correspond to (counting from 0) ")
    
    class Meta:
        verbose_name_plural = 'Time series'


class BaseExperimentalData(BaseModel):
    """
    Abstract base class for all data acquisition models. Never used directly.
    """
    session = models.ForeignKey(Session, related_name="%(app_label)s_%(class)s_related",
                                help_text="The Session to which this data belongs")

    class Meta:
        abstract = True
