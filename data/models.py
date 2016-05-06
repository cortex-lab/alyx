import uuid
from django.db import models
from polymorphic.models import PolymorphicModel
from django.contrib.postgres.fields import JSONField

from actions.models import Experiment
from misc.models import CoordinateTransformation, BrainLocation

class PhysicalArchive(models.Model):
    """A physical archive location - i.e. a room or cupboard"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.location

###############################################################################
### Data locations (local, server, archive)
###############################################################################

class DataRepository(PolymorphicModel):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    # TODO: type introspection for location type

    def get_valid_name(experiment_id=None):
        """TODO: Returns a default filepath for a new experiment. experiment_id
        must exist and be linked to a valid Subject."""
        pass

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "data repositories"

class LocalDataRepository(DataRepository):
    LOCATION_TYPES = (
        ('LF', 'Local Fast (SSD)'),
        ('LS', 'Local Slow (HDD)'),
    )

    hostname = models.CharField(max_length=1000, null=True, blank=True) # e.g. "NSLaptop"
    path = models.CharField(max_length=1000, null=True, blank=True) # e.g. 'D:/Data/acquisition/'

    class Meta:
        verbose_name_plural = "local data repositories"

class NetworkDataRepository(DataRepository):
    LOCATION_TYPES = (
        ('NF', 'Network Fast (SSD)'),
        ('NS', 'Network Slow (HDD)'),
    )

    # These will automatically be turned into browsable paths depending on the client and protocol.
    fqdn = models.CharField(max_length=1000, null=True, blank=True) # e.g. 1.2.3.4 or foxtrot.neuro.ucl.ac.uk
    share = models.CharField(max_length=1000, null=True, blank=True) # e.g. 'Data'
    path = models.CharField(max_length=1000, null=True, blank=True) # e.g. '/subjects/'
    nfs_supported = models.BooleanField() # NFS (Linux)
    smb_supported = models.BooleanField() # SMB (Windows)
    afp_supported = models.BooleanField() # AFP (Linux)

    def get_URIs(supported_protocols=None):
        """
        TODO: locator return function for all declared protocols e.g.
        (['\\foxtrot.neuro.ucl.ac.uk\Data\subjects\', 'smb'],
         ['afp://foxtrot.neuro.ucl.ac.uk/Data/subjects', 'afp'])
        """
        pass

    class Meta:
        verbose_name_plural = "network data repositories"

class ArchiveDataRepository(DataRepository):
    LOCATION_TYPES = (
        ('AF', 'Archive Fast (HDD)'),
        ('AS', 'Archive Slow (tape)'),
    )
    physical_archive = models.ForeignKey('PhysicalArchive')
    identifier = models.CharField(max_length=255, null=True, blank=True)

    # The tape may contain items other than tracked FileRecords. So we keep
    # track of the entire contents here to save iterating over the tape.
    tape_contents = JSONField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "archive data repositories"

###############################################################################
### Files and filetypes
###############################################################################

class FileRecord(models.Model):
    """A single file on disk or tape."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data_repository = models.ForeignKey('DataRepository')
    collection = models.ForeignKey('BaseFileCollection')

    # sequential ID in tape archive, if applicable. Can contain multiple records.
    tape_sequential_number = models.IntegerField(null=True, blank=True)


class BaseFileCollection(models.Model):
    """Collection of FileRecords corresponding to a single unique file."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    md5 = models.CharField(max_length=255, null=True, blank=True) # MD5 hash of file
    filename = models.CharField(max_length=1000)

    def __str__(self):
        return filename

    def get_all_locations(local_hostname=None):
        """TODO: return all valid network and archive file records for the Collection
        in order of speed. Return local records only where hostname matches input."""
        pass

