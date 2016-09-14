import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField, JSONField
from datetime import datetime, timezone
from subjects.models import Subject
from equipment.models import LabLocation, WeighingScale, VirusBatch
from misc.models import BrainLocation


class Action(models.Model):
    """
    Base class for an action performed on a subject, such as a recording; surgery;
    water control; weight measurement etc. This should normally be accessed through
    one of its subclasses.
    """
    SEVERITY_LIMITS = (
        (0, 'Mild'),
        (1, 'Moderate'),
        (2, 'Severe'),
        (3, 'Non-recovery')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    users = models.ManyToManyField(User, blank=True,
                                   help_text="The user(s) involved in this action")
    subject = models.ForeignKey(Subject, related_name='actions',
                                help_text="The subject on which this action was performed")
    location = models.ForeignKey(LabLocation, null=True, blank=True,
                                 help_text="The physical location at which the action was performed")
    procedures = models.ManyToManyField('Procedure', help_text="The procedure(s) performed")
    actual_severity = models.IntegerField(choices=SEVERITY_LIMITS,
                                          default=1, blank=True, null=True)
    narrative = models.TextField(null=True, blank=True)
    start_date_time = models.DateTimeField(null=True, blank=True, default=datetime.now)
    end_date_time = models.DateTimeField(null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=255), size=30,
                      null=True,
                      blank=True, help_text="Short text strings to allow searching")
    json = JSONField(null=True, blank=True, help_text="Structured data, formatted in a user-defined way")

    def __str__(self):
        return self.subject + " at " + self.start_date_time

class Protocol(models.Model):
    """
    An experimental protocol with a given severity limit.
    """
    SEVERITY_LIMITS = (
        (0, 'Mild'),
        (1, 'Moderate'),
        (2, 'Severe'),
        (3, 'Non-recovery')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="The protocol name")
    number = models.IntegerField(null=True, blank=True, help_text="The protocol number")
    severity_limit=models.IntegerField(choices=SEVERITY_LIMITS,
                                       default=1, blank=True, null=True)

    def __str__(self):
        return self.name

class Procedure(models.Model):
    """
    A procedure to be performed on a subject.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Short procedure name")
    protocol = models.ForeignKey('Protocol', null=True, blank=True, help_text="The associated protocol")
    description = models.TextField(null=True, blank=True, help_text="Detailed description of the procedure")

    def __str__(self):
        return self.name

class VirusInjection(Action):
    """
    A virus injection.
    """
    INJECTION_TYPES = (
        ('I', 'Iontophoresis'),
        ('P', 'Pressure'),
    )
    virus_batch = models.ForeignKey(VirusBatch, null=True, blank=True)
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

class WaterAdministration(Action):
    """
    For keeping track of water for subjects not on free water.
    """
    water_administered = models.FloatField(help_text="Water administered, in millilitres")

class Surgery(Action):
    """
    Surgery performed on a subject.
    """
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

