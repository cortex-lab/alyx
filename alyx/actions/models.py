import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField, JSONField
from datetime import datetime, timezone
from subjects.models import Subject
from equipment.models import LabLocation, WeighingScale, VirusBatch
from misc.models import BrainLocation


class ProcedureType(models.Model):
    """
    A procedure to be performed on a subject.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Short procedure name")
    description = models.TextField(null=True, blank=True, help_text="Detailed description of the procedure")

    def __str__(self):
        return self.name

class BaseAction(models.Model):
    """
    Base class for an action performed on a subject, such as a recording; surgery; etc.
    This should always be accessed through one of its subclasses.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    users = models.ManyToManyField(User, blank=True,
                                   help_text="The user(s) involved in this action")
    subject = models.ForeignKey(Subject, related_name="%(app_label)s_%(class)ss",
                                help_text="The subject on which this action was performed")
    location = models.ForeignKey(LabLocation, null=True, blank=True,
                                 help_text="The physical location at which the action was performed")
    procedures = models.ManyToManyField('ProcedureType', blank=True, help_text="The procedure(s) performed")
    narrative = models.TextField(null=True, blank=True)
    date_time = models.DateTimeField(null=True, blank=True, default=datetime.now)
    json = JSONField(null=True, blank=True, help_text="Structured data, formatted in a user-defined way")

    def __str__(self):
        return str(self.subject) + " at " + str(getattr(self, 'date_time', 'no time'))

    class Meta:
        abstract = True

class VirusInjection(BaseAction):
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

class Surgery(BaseAction):
    """
    Surgery performed on a subject.
    """
    brain_location = models.ForeignKey(BrainLocation, null=True, blank=True)

    class Meta:
        verbose_name_plural = "surgeries"

class Note(BaseAction):
    """
    A note about a subject.
    """
    pass

class Experiment(BaseAction):
    """
    An experiment or training session performed on a subject.
    """
    pass

class Weighing(models.Model):
    """
    A weighing of a subject.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, null=True, blank=True, help_text="The user who weighed the subject")
    subject = models.ForeignKey(Subject, related_name='weighings',
                                help_text="The subject which was weighed")
    date_time = models.DateTimeField(null=True, blank=True, default=datetime.now)
    json = JSONField(null=True, blank=True, help_text="Structured data, formatted in a user-defined way")
    weight = models.FloatField(help_text="Weight in grams")
    weighing_scale = models.ForeignKey(WeighingScale, null=True, blank=True,
                                       help_text="The scale record that was used to weigh the subject")

    def __str__(self):
        return str(self.subject) + " at " + str(self.date_time)

class WaterAdministration(models.Model):
    """
    For keeping track of water for subjects not on free water.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, null=True, blank=True, help_text="The user who administered water")
    subject = models.ForeignKey(Subject, related_name='water_administrations',
                                help_text="The subject to which water was administered")
    date_time = models.DateTimeField(null=True, blank=True, default=datetime.now)
    json = JSONField(null=True, blank=True, help_text="Structured data, formatted in a user-defined way")
    water_administered = models.FloatField(help_text="Water administered, in millilitres")

    def __str__(self):
        return str(self.subject) + " at " + str(self.date_time)

