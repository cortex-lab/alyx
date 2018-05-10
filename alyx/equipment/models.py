from django.db import models
from django.utils import timezone

from alyx.base import BaseModel, BasePolymorphicModel
from alyx.settings import TIME_ZONE


class Lab(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    institution = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(
        max_length=64, blank=True, default=TIME_ZONE,
        help_text="Timezone of the server "
        "(see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)")


class LabLocation(BaseModel):
    # minor but can we change this to Location or LabLocation? Because it could
    # also be a room in the animal house
    """
    The physical location at which an session is performed or appliances are located.
    This could be a room, a bench, a rig, etc.
    """
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Supplier(BasePolymorphicModel):
    """
    A company or individual that provides lab equipment or supplies.
    This is a base class, to be accessed by subclasses
    """
    name = models.CharField(max_length=255, help_text="i.e. 'NeuroNexus'")
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class EquipmentModel(BaseModel):
    """
    An equipment model. i.e. "BrainScanner 4X"
    """
    manufacturer = models.ForeignKey(
        Supplier, null=True, blank=True)
    model_name = models.CharField(
        max_length=255, help_text="e.g. 'BrainScanner 4X'")
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class VirusBatch(BaseModel):
    # i took out "provided by a supplier" because we make these ourselves
    # (they are diluated from what the supplier supplies)
    # might also need a location field (e.g. which fridge it is in) - let's
    # ask Charu
    """
    A virus batch
    """
    virus_type = models.CharField(max_length=255, blank=True,
                                  help_text="UPenn ID or equivalent")
    description = models.CharField(max_length=255, blank=True)
    virus_source = models.ForeignKey(Supplier, null=True, blank=True,
                                     help_text="Who supplied the virus")
    date_time_made = models.DateTimeField(
        null=True, blank=True, default=timezone.now)
    nominal_titer = models.FloatField(
        null=True, blank=True, help_text="TODO: What unit?")
    # let's ask Charu about what unit.

    class Meta:
        verbose_name_plural = "virus batches"


###############################################################################
# Appliances
###############################################################################

class Appliance(BasePolymorphicModel):
    # If someone buys a new piece of equipment that doesn't belong in any of the subclasses,
    # can they just add it
    # as an Appliance, with no subclass?
    #
    # also, when you have two of one appliance, do they both get entries here?
    """
    An appliance, provided by a specific manufacturer. This class is only accessed through
    its subclasses.
    """
    location = models.ForeignKey('LabLocation', null=True, blank=True,
                                 help_text="The physical location of the appliance.")
    equipment_model = models.ForeignKey('EquipmentModel')
    serial = models.CharField(max_length=255, blank=True,
                              help_text="The serial number of the appliance.")
    description = models.TextField(blank=True)

    descriptive_name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        if self.descriptive_name:
            return self.descriptive_name
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
    An amplifier used in electrophysiology sessions.
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
