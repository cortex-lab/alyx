import uuid
from django.db import models
from django.contrib.auth.models import User
from polymorphic.models import PolymorphicModel

from django.contrib.postgres.fields import JSONField



class Supplier(PolymorphicModel)	
	"""
    A company or individual that provides lab equipment or supplies. 
	This is a base class, to be accessed by subclasses
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="i.e. 'NeuroNexus'")
    notes = models.TextField(null=True, blank=True)
    
	def __str__(self):
        return self.name
		
class EquipmentManufacturer(Supplier):
# maybe this could be a subclass of a more general supplier field? 
    """
    An equipment manufacturer, i.e. "NeuroNexus"
    """
	pass
	
class VirusSource(Supplier):
# maybe this could be a subclass of a more general supplier field? 
    """
    An equipment manufacturer, i.e. "NeuroNexus"
    """
	pass
	
class EquipmentModel(models.Model):
    """
    An equipment model. i.e. "BrainScanner 4X"
    """
    manufacturer = models.ForeignKey('EquipmentManufacturer', null=True, blank=True)
    model_name = models.CharField(max_length=255, help_text="e.g. 'BrainScanner 4X'")
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name
		
class VirusBatch(models.Model):
# i took out "provided by a supplier" because we make these ourselves (they are diluated from what the supplier supplies)    
# might also need a location field (e.g. which fridge it is in) - let's ask Charu
	"""
    A virus batch
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    virus_type =  models.CharField(max_length=255, null=True, blank=True,
                                   help_text="UPenn ID or equivalent")
    description = models.CharField(max_length=255, null=True, blank=True)
    virus_source = models.ForeignKey('VirusSource', null=True, blank=True
                                    help_text="Who supplied the virus")
    date_time_made = models.DateTimeField(null=True, blank=True, default=datetime.now)
    nominal_titer = models.FloatField(null=True, blank=True, help_text="TODO: What unit?") 
	# let's ask Charu about what unit.

    class Meta:
        verbose_name_plural = "virus batches"

###############################################################################
### Appliances
###############################################################################

class Appliance(PolymorphicModel):
	# If someone buys a new piece of equipment that doesn't belong in any of the subclasses, can they just add it 
	# as an Appliance, with no subclass?
	#
	# also, when you have two of one appliance, do they both get entries here?
    """
    An appliance, provided by a specific manufacturer. This class is only accessed through its subclasses.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey('LabLocation', null=True, blank=True,
                                 help_text="The physical location of the appliance.")
    equipment_model = models.ForeignKey('EquipmentModel')
    serial = models.CharField(max_length=255, null=True, blank=True,
                              help_text="The serial number of the appliance.")
    notes = models.TextField(null=True, blank=True)
    json = JSONField(null=True, blank=True)

    descriptive_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        if descriptive_name:
            return descriptive_name
        else:
            return "{0} {1}, location {2}".format(self.equipment_model,
                                                  self.id[:4],
                                                  self.location)

class WeighingScale(Appliance):
    """
    A weighing scale.
    """
    pass
	
class LightSource(Appliance):
    """
    A light source (e.g. for use in optogenetics.
    """
	# TYPE = 'Laser' or 'LED'
	# wavelength : numeric
	# max_power : numeric
    pass

class Amplifier(Appliance):
    """
    An amplifier used in electrophysiology experiments.
    """
    pass

class PipettePuller(Appliance):
    """
    A pipette puller for intracellular electrophysiology.
    """
    pass

class DAQ(Appliance):
    """
    A DAQ for extracellular electrophysiology.
    """
    pass

class ExtracellularProbe(Appliance):
    """
    An extracellular probe used in extracellular electrophysiology.
    """
    prb = JSONField(null=True, blank=True, help_text=
		"A JSON string describing the probe connectivity and geometry. For details, see https://github.com/klusta-team/kwiklib/wiki/Kwik-format#prb")
	# does this mean a pointer to a .prb file on disk, or a copy of it in the database? (I guess the latter)
