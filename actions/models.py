import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField, JSONField
from datetime import datetime, timezone
from subjects.models import Subject

class Action(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    users = models.ManyToManyField(User, blank=True)
    subject = models.ForeignKey(Subject, related_name='actions')
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
    virus_batch = models.ForeignKey('Virus_Batch') # links to virus_batch document, defined below
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
