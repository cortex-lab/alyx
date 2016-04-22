import uuid
from django.db import models
from django.contrib.auth.models import User

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

class Appliance(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	location = models.ForeignKey('Location')
	manufacturer_model = models.CharField(max_length=255, null=True, blank=True)
	serial = models.CharField(max_length=255, null=True, blank=True)
	notes = models.TextField(null=True, blank=True)

	descriptive_name = models.CharField(max_length=255, null=True, blank=True)

	def __str__(self):
		if descriptive_name:
			return descriptive_name
		else:
			return "{0}, location {1}".format(self.id[:6], self.location)

class WeighingScale(Appliance):
	pass