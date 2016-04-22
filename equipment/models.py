import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField

class Location(models.Model):
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
	type = models.CharField(max_length=1, choices=CAGE_TYPES, default='R')
	location = models.ForeignKey('Location')

class EquipmentManufacturer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

class EquipmentModel(models.Model):
	manufacturer = models.ForeignKey('EquipmentManufacturer', null=True, blank=True)
	model_name = models.CharField(max_length=255)
	description = models.CharField(max_length=255, null=True, blank=True)

	def __str__(self):
		return self.name

###############################################################################
### Appliances
###############################################################################

class Appliance(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	location = models.ForeignKey('Location', null=True, blank=True)
	equipment_model = models.ForeignKey('EquipmentModel')
	serial = models.CharField(max_length=255, null=True, blank=True)
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
	pass

class Amplifier(Appliance):
	pass

class ExtracellularProbe(Appliance):
	prb = JSONField(null=True, blank=True)

