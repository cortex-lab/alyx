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
    """
    Base class for a file storage device; this could be a local hard-drive on a laptop,
    a network file location, or an offline archive tape / Blu-Ray disc / hard-drive.
    """
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
    """
    A local data repository on a single computer.
    """
    hostname = models.CharField(max_length=1000, null=True, blank=True,
                                help_text="Hostname must be unique. e.g. 'NSLaptop'")
    path = models.CharField(max_length=1000, null=True, blank=True,
                            help_text="e.g. 'D:/Data/acquisition/'")

    class Meta:
        verbose_name_plural = "local data repositories"

class NetworkDataRepository(DataRepository):
    """
    A network data repository, accessible over several different protocols.
    This will be be turned into a browsable path depending on the client and protocol.
    """
    fqdn = models.CharField(max_length=1000, null=True, blank=True,
                            help_text="Fully Qualified Domain Name or IP, e.g. 1.2.3.4 or foxtrot.neuro.ucl.ac.uk")
    share = models.CharField(max_length=1000, null=True, blank=True, help_text="Share name, e.g. 'Data'")
    path = models.CharField(max_length=1000, null=True, blank=True, help_text="Path name after share, e.g. '/subjects/'")
    nfs_supported = models.BooleanField(help_text="NFS supported (Linux)")
    smb_supported = models.BooleanField(help_text="SMB supported (Windows)")
    afp_supported = models.BooleanField(help_text="AFP supported (Linux)")

    def get_URIs(supported_protocols=None):
        """
        TODO: locator return function for all declared protocols e.g.::

            (['\\foxtrot.neuro.ucl.ac.uk\Data\subjects\', 'smb'],
             ['afp://foxtrot.neuro.ucl.ac.uk/Data/subjects', 'afp'])
        """
        pass

    class Meta:
        verbose_name_plural = "network data repositories"

class ArchiveDataRepository(DataRepository):
    """
    An archive, offline or near-line, data repository. This could be a hard-drive
    in a cupboard, or tape or DVD/CD/Blu-Ray.
    If a tape, the tape may contain items other than tracked FileRecords. So we keep
    track of the entire contents here to save iterating over the tape.
    """

    physical_archive = models.ForeignKey('PhysicalArchive')
    identifier = models.CharField(max_length=255, null=True, blank=True)
    tape_contents = JSONField(null=True, blank=True, help_text="Tape contents, including untracked files.")

    class Meta:
        verbose_name_plural = "archive data repositories"

    def __str__(self):
        return identifier

###############################################################################
### Files and filetypes
###############################################################################

class FileRecord(models.Model):
    """A single file on disk or tape."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    dataset = models.ForeignKey('Dataset', related_name='file_records')
    filename = models.CharField(max_length=1000, help_text="Full filename or UNC filepath")
    # data_repository = models.ForeignKey('DataRepository')
    # file = models.ForeignKey('LogicalFile')


    # tape_sequential_number = models.IntegerField(null=True, blank=True,
                                                 # help_text="sequential ID in tape archive, if applicable. Can contain multiple records.")
    def __str__(self):
        return filename

# class LogicalFile(models.Model):
#     """A single file or folder. Can be stored in several places (several FileRecords)
#     which all share the same filename and hash."""
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     md5 = models.CharField(max_length=255, null=True, blank=True, help_text="MD5 hash, if a file")
#     filename = models.CharField(max_length=1000)
#     is_folder = models.BooleanField(help_text="True if the LogicalFile is a folder, not a single file.")
#     fileset = models.ForeignKey('Dataset', help_text="The Fileset that this file belongs to.")

#     def __str__(self):
#         return filename

#     def get_all_locations(local_hostname=None):
#         """TODO: return all valid network and archive file records for the Collection
#         in order of speed. Return local records only where hostname matches input."""
#         pass

class Dataset(models.Model):
    """Collection of LogicalFiles (files or folders) grouped together."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    experiment = models.ForeignKey(Experiment, related_name="%(app_label)s_%(class)s_related",
                                   help_text="The Experiment to which this data belongs")

    def __str__(self):
        return self.name

class BaseExperimentalData(models.Model):
    """
    Abstract base class for all data acquisition models. Never used directly.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    experiment = models.ForeignKey(Experiment, related_name="%(app_label)s_%(class)s_related",
                                   help_text="The Experiment to which this data belongs")

    class Meta:
        abstract = True
