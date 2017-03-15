from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import datetime
from equipment.models import LabLocation, WeighingScale, VirusBatch
from misc.models import BrainLocation
from alyx.base import BaseModel


class ProcedureType(BaseModel):
    """
    A procedure to be performed on a subject.
    """
    name = models.CharField(max_length=255, help_text="Short procedure name")
    description = models.TextField(blank=True,
                                   help_text="Detailed description "
                                   "of the procedure")

    def __str__(self):
        return self.name


class Weighing(BaseModel):
    """
    A weighing of a subject.
    """
    user = models.ForeignKey(User, null=True, blank=True,
                             help_text="The user who weighed the subject")
    subject = models.ForeignKey('subjects.Subject', related_name='weighings',
                                help_text="The subject which was weighed")
    date_time = models.DateTimeField(
        null=True, blank=True, default=datetime.now)
    weight = models.FloatField(help_text="Weight in grams")
    weighing_scale = models.ForeignKey(WeighingScale, null=True, blank=True,
                                       help_text="The scale record that was used "
                                       "to weigh the subject")

    def __str__(self):
        return '%s at %s (%.1f g)' % (str(self.subject),
                                      str(self.date_time),
                                      self.weight,
                                      )


class WaterAdministration(BaseModel):
    """
    For keeping track of water for subjects not on free water.
    """
    user = models.ForeignKey(User, null=True, blank=True,
                             help_text="The user who administered water")
    subject = models.ForeignKey('subjects.Subject',
                                related_name='water_administrations',
                                help_text="The subject to which water was administered")
    date_time = models.DateTimeField(null=True, blank=True,
                                     default=datetime.now)
    water_administered = models.FloatField(help_text="Water administered, in millilitres")
    hydrogel = models.NullBooleanField()

    def __str__(self):
        return str(self.subject) + " at " + str(self.date_time)


class BaseAction(BaseModel):
    """
    Base class for an action performed on a subject, such as a recording;
    surgery; etc. This should always be accessed through one of its subclasses.
    """

    users = models.ManyToManyField(User, blank=True,
                                   help_text="The user(s) involved in this action")
    subject = models.ForeignKey('subjects.Subject',
                                related_name="%(app_label)s_%(class)ss",
                                help_text="The subject on which this action was performed")
    location = models.ForeignKey(LabLocation, null=True, blank=True,
                                 help_text="The physical location at which the action was "
                                 "performed")
    procedures = models.ManyToManyField('ProcedureType', blank=True,
                                        help_text="The procedure(s) performed")
    narrative = models.TextField(blank=True)
    start_time = models.DateTimeField(null=True, blank=True, default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (str(self.subject) + " at " +
                str(getattr(self, 'start_time', 'no time')))

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
    injection_volume = models.FloatField(
        null=True, blank=True, help_text="Volume in nanoliters")
    rate_of_injection = models.FloatField(
        null=True, blank=True, help_text="TODO: Nanoliters per second / per minute?")
    injection_type = models.CharField(max_length=1,
                                      choices=INJECTION_TYPES,
                                      default='I', blank=True,
                                      help_text="Whether the injection was through "
                                      "iontophoresis or pressure")


class Surgery(BaseAction):
    """
    Surgery performed on a subject.
    """
    OUTCOME_TYPES = (
        ('a', 'Acute'),
        ('r', 'Recovery'),
    )
    brain_location = models.ForeignKey(BrainLocation, null=True, blank=True)
    outcome_type = models.CharField(max_length=1,
                                    choices=OUTCOME_TYPES,
                                    blank=True,
                                    )

    class Meta:
        verbose_name_plural = "surgeries"

    def save(self, *args, **kwargs):
        if self.outcome_type == 'a' and self.start_time:
            self.subject.death_date = self.start_time.date()
            self.subject.save()
        return super(Surgery, self).save(*args, **kwargs)


class Session(BaseAction):
    """
    An session or training session performed on a subject.
    """
    pass


class WaterRestriction(BaseAction):
    """
    Another type of action.
    """
    pass


class OtherAction(BaseAction):
    """
    Another type of action.
    """
    pass
