from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from alyx.base import BaseModel
from equipment.models import LabLocation, Lab, WeighingScale, VirusBatch
from misc.models import BrainLocation, OrderedUser


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
    user = models.ForeignKey(OrderedUser, null=True, blank=True, on_delete=models.SET_NULL,
                             help_text="The user who weighed the subject")
    subject = models.ForeignKey('subjects.Subject', related_name='weighings',
                                on_delete=models.CASCADE,
                                help_text="The subject which was weighed")
    date_time = models.DateTimeField(
        null=True, blank=True, default=timezone.now)
    weight = models.FloatField(validators=[MinValueValidator(limit_value=0)],
                               help_text="Weight in grams")
    weighing_scale = models.ForeignKey(WeighingScale, null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       help_text="The scale record that was used "
                                       "to weigh the subject")

    def expected(self):
        """Expected weighing."""
        from .water import expected_weighing
        return expected_weighing(self.subject, self.date_time)

    def __str__(self):
        return 'Weighing %.2f g for %s' % (self.weight,
                                           str(self.subject),
                                           )


class WaterAdministration(BaseModel):
    """
    For keeping track of water for subjects not on free water.
    """
    user = models.ForeignKey(OrderedUser, null=True, blank=True,
                             on_delete=models.SET_NULL,
                             help_text="The user who administered water")
    subject = models.ForeignKey('subjects.Subject',
                                on_delete=models.CASCADE,
                                related_name='water_administrations',
                                help_text="The subject to which water was administered")
    date_time = models.DateTimeField(null=True, blank=True,
                                     default=timezone.now)
    water_administered = models.FloatField(validators=[MinValueValidator(limit_value=0)],
                                           help_text="Water administered, in millilitres")
    hydrogel = models.NullBooleanField()

    def expected(self):
        from .water import water_requirement_total
        return water_requirement_total(self.subject, date=self.date_time)

    def __str__(self):
        return 'Water %.2fg for %s' % (self.water_administered,
                                       str(self.subject),
                                       )


class BaseAction(BaseModel):
    """
    Base class for an action performed on a subject, such as a recording;
    surgery; etc. This should always be accessed through one of its subclasses.
    """

    users = models.ManyToManyField(OrderedUser, blank=True,
                                   help_text="The user(s) involved in this action")
    subject = models.ForeignKey('subjects.Subject',
                                on_delete=models.CASCADE,
                                related_name="%(app_label)s_%(class)ss",
                                help_text="The subject on which this action was performed")
    location = models.ForeignKey(LabLocation, null=True, blank=True, on_delete=models.SET_NULL,
                                 help_text="The physical location at which the action was "
                                 "performed")
    lab = models.ForeignKey(Lab, null=True, blank=True, on_delete=models.SET_NULL)
    procedures = models.ManyToManyField('ProcedureType', blank=True,
                                        help_text="The procedure(s) performed")
    narrative = models.TextField(blank=True)
    start_time = models.DateTimeField(
        null=True, blank=True, default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return '%s for %s' % (self.__class__.__name__, self.subject)

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
    virus_batch = models.ForeignKey(VirusBatch, null=True, blank=True, on_delete=models.SET_NULL,)
    injection_volume = models.FloatField(
        null=True, blank=True, help_text="Volume in nanoliters")
    rate_of_injection = models.FloatField(
        null=True, blank=True, help_text="TODO: Nanoliters per second / per minute?")
    injection_type = models.CharField(max_length=1,
                                      choices=INJECTION_TYPES,
                                      default='I', blank=True,
                                      help_text="Whether the injection was through "
                                      "iontophoresis or pressure")


def _default_surgery_location():
    s = LabLocation.objects.filter(name='Surgery Room')
    if s:
        return s[0].pk
    return None


class Surgery(BaseAction):
    """
    Surgery performed on a subject.
    """
    OUTCOME_TYPES = (
        ('a', 'Acute'),
        ('r', 'Recovery'),
    )
    brain_location = models.ForeignKey(BrainLocation, null=True, blank=True,
                                       on_delete=models.SET_NULL,)
    outcome_type = models.CharField(max_length=1,
                                    choices=OUTCOME_TYPES,
                                    blank=True,
                                    )
    location = models.ForeignKey(LabLocation, null=True, blank=True,
                                 on_delete=models.SET_NULL,
                                 default=_default_surgery_location,
                                 help_text="The physical location at which the surgery was "
                                 "performed")

    class Meta:
        verbose_name_plural = "surgeries"

    def save(self, *args, **kwargs):
        if self.outcome_type == 'a' and self.start_time:
            self.subject.death_date = self.start_time.date()
            self.subject.save()
        return super(Surgery, self).save(*args, **kwargs)


# WE ARE CONSIDERING RENAMING SESSION TO EXPERIMENT.
class Session(BaseAction):
    """
    A recording or training session performed on a subject. There is normally only one of
    these per day, for example corresponding to a  period of uninterrupted head fixation.

    Note that you can organize sessions hierarchically by assigning a parent_session.
    Sub-sessions could for example corresponding to periods of time in which the same
    neurons were recorded, or a particular set of stimuli were presented. Top-level sessions
    should have parent_session set to null.

    If the fields (e.g. users) of a subsession are null, they should inherited from the parent.
    """
    parent_session = models.ForeignKey('Session', null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       help_text="Hierarchical parent to this session")
    project = models.ForeignKey('subjects.Project', null=True, blank=True,
                                on_delete=models.SET_NULL)
    type = models.CharField(max_length=255, null=True, blank=True,
                            help_text="User-defined session type (e.g. Base, Experiment)")
    number = models.IntegerField(null=True, blank=True,
                                 help_text="Optional session number for this level")

    def save(self, *args, **kwargs):
        # Default project is the subject's project.
        if not self.project_id:
            self.project = self.subject.projects.first()
        return super(Session, self).save(*args, **kwargs)

    def __str__(self):
        return "Session %s for %s" % (str(self.pk)[:8], self.subject)


class WaterRestriction(BaseAction):
    """
    Water restriction.
    """

    def is_active(self):
        return self.start_time is not None and self.end_time is None


class OtherAction(BaseAction):
    """
    Another type of action.
    """
    pass
