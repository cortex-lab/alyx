import uuid
from django.db import models
from django.contrib.auth.models import User

class Subject(models.Model):
	# Allowable species
    MOUSE = 'MO'
    RAT = 'RA'
    RHESUS_MACAQUE = 'RM'
    HUMAN =	'HU'

    SPECIES = (
        (MOUSE, 'Laboratory mouse'),
        (RAT, 'Laboratory rat'),
        (RHESUS_MACAQUE, 'Rhesus macaque'),
        (HUMAN, 'Human')
    )

    SEXES = (
    	('M', 'Male'),
    	('F', 'Female'),
    	('U', 'Unknown')
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nickname = models.CharField(max_length=255)
    species = models.CharField(max_length=2,
    						   choices=SPECIES,
    						   default=MOUSE)
    sex = models.CharField(max_length=1,
                           choices=SEXES, default='U')
    strain = models.CharField(max_length=255)
    genotype = models.CharField(max_length=255)
    source = models.CharField(max_length=255)
    birth_date_time = models.DateTimeField(null=True, blank=True)
    death_date_time = models.DateTimeField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, related_name = 'subjects_responsible')

    notes = models.TextField(null=True, blank=True)

    def dead(self):
        return self.death_date_time is not None
    dead.boolean = True

    def __str__(self):
        return self.nickname

class Experiment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    start_date_time = models.DateTimeField()
    location = models.CharField(max_length=255)


    def __str__(self):
        return self.id[:5]
