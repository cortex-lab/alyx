import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField, JSONField
from datetime import datetime, timezone
from subjects.models import Subject
from equipment.models import ExperimentLocation, WeighingScale
from misc.models import BrainLocation

class VirusBatch(models.Model):
    """
    A virus batch provided by a supplier.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    virus_type =  models.CharField(max_length=255, null=True, blank=True,
                                   help_text="UPenn ID or equivalent")
    description = models.CharField(max_length=255, null=True, blank=True)
    virus_source = models.CharField(max_length=255, null=True, blank=True,
                                    help_text="Who sold the virus. TODO: make this a normalized table")
    date_time_made = models.DateTimeField(null=True, blank=True, default=datetime.now)
    nominal_titer = models.FloatField(null=True, blank=True, help_text="TODO: What unit?")

    class Meta:
        verbose_name_plural = "virus batches"

class Action(models.Model):
    """
    Base class for an action performed on a subject, such as a recording; surgery;
    water control; weight measurement etc. This should normally be accessed through
    one of its subclasses.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    users = models.ManyToManyField(User, blank=True,
                                   help_text="The user(s) involved in this action")
    subject = models.ForeignKey(Subject, related_name='actions',
                                help_text="The subject on which this action was performed")
    location = models.ForeignKey(ExperimentLocation, null=True, blank=True,
                                 help_text="The physical location at which the experiment was performed")
    narrative = models.TextField(null=True, blank=True)
    start_date_time = models.DateTimeField(null=True, blank=True, default=datetime.now)
    end_date_time = models.DateTimeField(null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=255), size=30,
                      null=True,
                      blank=True)
    json = JSONField(null=True, blank=True)


class VirusInjection(Action):
    """
    A virus injection.
    """
    INJECTION_TYPES = (
        ('I', 'Iontophoresis'),
        ('P', 'Pressure'),
    )
    virus_batch = models.ForeignKey('VirusBatch')
    injection_volume = models.FloatField(null=True, blank=True, help_text="Volume in nanoliters")
    rate_of_injection = models.FloatField(null=True, blank=True, help_text="TODO: Nanoliters per second / per minute?")
    injection_type = models.CharField(max_length=1,
                                     choices=INJECTION_TYPES,
                                     default='I', blank=True, null=True,
                                     help_text="Whether the injection was through iontophoresis or pressure")

class Weighing(Action):
    """
    A weighing of a subject.
    """
    weight = models.FloatField(help_text="Weight in grams")
    weighing_scale = models.ForeignKey(WeighingScale, null=True, blank=True,
                                       help_text="The scale record that was used to weigh the subject")

class Surgery(Action):
    """
    Surgery performed on a subject.
    """
    procedure = models.CharField(max_length=255, null=True, blank=True,
                                 help_text="The type of procedure(s) performed")
    brain_location = models.ForeignKey(BrainLocation, null=True, blank=True)

    class Meta:
        verbose_name_plural = "surgeries"

class Note(Action):
    """
    A note about a subject.
    """
    pass

class Experiment(Action):
    """
    An experiment or training session performed on a subject.
    """
    pass

