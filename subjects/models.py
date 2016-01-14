import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField, JSONField
from datetime import datetime

###############################################################################
### Subjects
###############################################################################

class Species(models.Model):
    binomial = models.CharField(max_length=255, primary_key=True)
    display_name = models.CharField(max_length=255)

    def __str__(self):
        return self.display_name

    class Meta:
        verbose_name_plural = "species"

class Subject(models.Model):
    SEXES = (
    	('M', 'Male'),
    	('F', 'Female'),
    	('U', 'Unknown')
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nickname = models.CharField(max_length=255, null=True, blank=True)
    species = models.ForeignKey(Species)
    litter = models.ForeignKey('Litter', null=True)
    sex = models.CharField(max_length=1,
                           choices=SEXES, default='U')
    strain = models.CharField(max_length=255, null=True, blank=True)
    genotype = models.CharField(max_length=255, null=True, blank=True)
    source = models.CharField(max_length=255, null=True, blank=True)
    birth_date_time = models.DateTimeField(null=True, blank=True)
    death_date_time = models.DateTimeField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, related_name = 'subjects_responsible', null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    def alive(self):
        return self.death_date_time is None
    alive.boolean = True

    def __str__(self):
        return self.nickname

class Litter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descriptive_name = models.CharField(max_length=255)
    mother = models.ForeignKey("Subject", null=True, blank=True, related_name="litter_mother")
    father = models.ForeignKey("Subject", null=True, blank=True, related_name="litter_father")


###############################################################################
### Actions
###############################################################################

class Action(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    users = models.ManyToManyField(User, blank=True)
    subject = models.ForeignKey(Subject)
    location = models.CharField(max_length=255, null=True, blank=True)
    narrative = models.TextField(null=True, blank=True)
    start_date_time = models.DateTimeField(null=True, blank=True, default=datetime.now)
    end_date_time = models.DateTimeField(null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=255), size=30,
                      null=True,
                      blank=True)
    JSON = JSONField(null=True, blank=True)


class Virus_Batch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    virus_type =  models.CharField(max_length=255, null=True, blank=True) # upenn ID or equivalent
    description = models.CharField(max_length=255, null=True, blank=True)
    virus_source = models.CharField(max_length=255, null=True, blank=True) # who sold it
    date_time_made = models.DateTimeField(null=True, blank=True, default=datetime.now)
    nominal_titer = models.FloatField(null=True, blank=True)

class Virus_Injection(Action):
    INJECTION_TYPES = (
        ('I', 'Iontophoresis'),
        ('P', 'Pressure'),
    )
    virus_batch_id = models.ForeignKey('Virus_Batch') # links to virus_batch document, defined below
    injection_volume = models.FloatField(null=True, blank=True)
    rate_of_injection = models.FloatField(null=True, blank=True)
    injection_type = models.CharField(max_length=1,
                                     choices=INJECTION_TYPES,
                                     default='I', blank=True, null=True)

class Weighing(Action):
    weight = models.FloatField()

class Note(Action):
    pass

class Surgery(Action):
    procedure = models.CharField(max_length=255, null=True, blank=True)
    brain_location = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name_plural = "surgeries"