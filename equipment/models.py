import uuid
from django.db import models
from django.contrib.auth.models import User
from polymorphic.models import PolymorphicModel

from django.contrib.postgres.fields import JSONField

class ExperimentLocation(models.Model):
    """
    The physical location at which an experiment is performed or appliances are located.
    This could be a room, a bench, a rig, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Cage(models.Model):
    CAGE_TYPES = (
        ('R', 'Regular'),
        ('I', 'IVC'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=1, choices=CAGE_TYPES, default='R', help_text=
                            "Is this an IVC or regular cage?")
    location = models.ForeignKey('ExperimentLocation')

class EquipmentManufacturer(models.Model):
    """
    An equipment manufacturer, i.e. "NeuroNexus"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="i.e. 'NeuroNexus'")
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

class EquipmentModel(models.Model):
    """
    An equipment model. i.e. "BrainScanner 4X"
    """
    manufacturer = models.ForeignKey('EquipmentManufacturer', null=True, blank=True)
    model_name = models.CharField(max_length=255, help_text="e.g. 'BrainScanner 4X'")
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

###############################################################################
### Appliances
###############################################################################

class Appliance(PolymorphicModel):
    """
    An appliance, provided by a specific manufacturer. This class is only accessed through its subclasses.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey('ExperimentLocation', null=True, blank=True,
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

class Amplifier(Appliance):
    """
    An amplifier used in electrophysiology experiments.
    """
    pass

class ExtracellularProbe(Appliance):
    """
    An extracellular probe used in extracellular electrophysiology.
    """
    prb = JSONField(null=True, blank=True, help_text="The PRB file describing the probe connectivity and geometry, in JSON")

