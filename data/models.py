import uuid
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField

class PhysicalArchive(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.location

###############################################################################
### Data locations (local, server, archive)
###############################################################################

class DataLocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # TODO: type introspection for location type

class LocalDataLocation(DataLocation):
	LOCATION_TYPES = (
    	('LF', 'Local Fast (SSD)'),
    	('LS', 'Local Slow (HDD)'),
    )

	hostname = models.CharField(max_length=1000, null=True, blank=True) # e.g. "NSLaptop"
	path = models.CharField(max_length=1000, null=True, blank=True) # e.g. 'D:/Data/acquisition/'

class NetworkDataLocation(DataLocation):
	LOCATION_TYPES = (
    	('NF', 'Network Fast (SSD)'),
    	('NS', 'Network Slow (HDD)'),
    )

    # These will automatically be turned into browsable paths depending on the client and protocol.
	fqdn = models.CharField(max_length=1000, null=True, blank=True) # e.g. 1.2.3.4 or foxtrot.neuro.ucl.ac.uk
	share = models.CharField(max_length=1000, null=True, blank=True) # e.g. 'Data'
	path = models.CharField(max_length=1000, null=True, blank=True) # e.g. '/multichanspikes/'
	nfs_supported = models.BooleanField() # NFS (Linux)
	smb_supported = models.BooleanField() # SMB (Windows)
	afp_supported = models.BooleanField() # AFP (Linux)

	# TODO: write locator return function for all declared protocols e.g.
	# (['\\foxtrot.neuro.ucl.ac.uk\Data\multichanspikes\', 'smb'],
	#  ['afp://foxtrot.neuro.ucl.ac.uk/Data/multichanspikes'])

class ArchiveDataLocation(DataLocation):
	LOCATION_TYPES = (
    	('AF', 'Archive Fast (HDD)'),
    	('AS', 'Archive Slow (tape)'),
    )
	physical_archive = models.ForeignKey('PhysicalArchive')
	identifier = models.CharField(max_length=255, null=True, blank=True)

	# The tape may contain items other than tracked file records. So we keep
	# track of the entire contents here to save iterating over the tape.
	tape_contents = JSONField(null=True, blank=True)

###############################################################################
### Files and filetypes
###############################################################################

class FileRecord(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	filename = models.CharField(max_length=1000)
	data_location = models.ForeignKey('DataLocation')

	is_folder = models.BooleanField() # if True, indicates 'filename' is a folder
	tape_sequential_number = models.IntegerField(null=True, blank=True) # tape record sequential ID
	md5 = models.CharField(max_length=255, null=True, blank=True) # MD5 hash of file

	def __str__(self):
		return filename
