import csv
from datetime import datetime
import logging
import os.path as op
import urllib

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone

from alyx.base import BaseModel
from equipment.models import LabLocation
from actions.models import WaterRestriction, Weighing, WaterAdministration

logger = logging.getLogger(__name__)


MOUSE_SPECIES_ID = 'c8339f4f-4afe-49d5-b2a2-a7fc61389aaf'
DEFAULT_RESPONSIBLE_USER_ID = 5


class Subject(BaseModel):
    """Metadata about an experimental subject (animal or human)."""
    SEXES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('U', 'Unknown')
    )
    SEVERITY_CHOICES = (
        ('st', 'Sub-threshold'),
        ('mi', 'Mild'),
        ('mo', 'Moderate'),
        ('se', 'Severe'),
        ('nr', 'Non-recovery'),
    )
    PROTOCOL_NUMBERS = tuple((str(i), str(i)) for i in range(1, 5))

    nickname = models.CharField(max_length=255,
                                unique=True,
                                default='-',
                                help_text="Easy-to-remember, unique name "
                                          "(e.g. 'Hercules').")
    species = models.ForeignKey('Species', null=True, blank=True, on_delete=models.SET_NULL,
                                default=MOUSE_SPECIES_ID)
    litter = models.ForeignKey('Litter', null=True, blank=True, on_delete=models.SET_NULL)
    sex = models.CharField(max_length=1, choices=SEXES,
                           blank=True, default='U')
    strain = models.ForeignKey('Strain', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               )
    genotype = models.ManyToManyField('Allele', through='Zygosity')
    genotype_test = models.ManyToManyField('Sequence', through='GenotypeTest')
    source = models.ForeignKey('Source', null=True, blank=True, on_delete=models.SET_NULL)
    line = models.ForeignKey('Line', null=True, blank=True, on_delete=models.SET_NULL)
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)
    wean_date = models.DateField(null=True, blank=True)
    genotype_date = models.DateField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                         default=DEFAULT_RESPONSIBLE_USER_ID,
                                         related_name='subjects_responsible',
                                         help_text="Who has primary or legal responsibility "
                                         "for the subject.")
    cage = models.ForeignKey('Cage', null=True, blank=True, on_delete=models.SET_NULL)
    request = models.ForeignKey('SubjectRequest', null=True, blank=True,
                                on_delete=models.SET_NULL)
    implant_weight = models.FloatField(null=True, blank=True, help_text="Implant weight in grams")
    ear_mark = models.CharField(max_length=32, blank=True)
    protocol_number = models.CharField(max_length=1, choices=PROTOCOL_NUMBERS, default='3')
    notes = models.TextField(blank=True)

    cull_method = models.TextField(blank=True)
    adverse_effects = models.TextField(blank=True)
    actual_severity = models.CharField(max_length=2, choices=SEVERITY_CHOICES,
                                       blank=True)

    class Meta:
        ordering = ['-birth_date', 'nickname']

    def __init__(self, *args, **kwargs):
        super(Subject, self).__init__(*args, **kwargs)
        # Used to detect when the request has changed.
        self._original_request = self.request

    def alive(self):
        return self.death_date is None
    alive.boolean = True

    def nicknamesafe(self):
        return urllib.parse.quote(str(self.nickname), '')

    def age_days(self):
        if (self.death_date is None and self.birth_date is not None):
            # subject still alive
            age = datetime.now(timezone.utc).date() - self.birth_date
        elif (self.death_date is not None and self.birth_date is not None):
            # subject is dead
            age = self.death_date - self.birth_date
        else:
            # not dead or born!
            return None
        return age.days

    def age_weeks(self):
        return (self.age_days() or 0) // 7

    def mother(self):
        if self.litter:
            return self.litter.mother

    def father(self):
        if self.litter:
            return self.litter.father

    def water_restriction_date(self):
        restriction = WaterRestriction.objects.filter(subject__id=self.id)
        restriction = restriction.order_by('-start_time')
        if not restriction:
            return
        return restriction[0].start_time

    def reference_weighing(self):
        wr_date = self.water_restriction_date()
        weighings = Weighing.objects.filter(subject__id=self.id,
                                            date_time__lte=wr_date)
        weighings = weighings.order_by('-date_time')
        if not weighings:
            return 0
        return weighings[0].weight

    def current_weighing(self):
        weighings = Weighing.objects.filter(subject__id=self.id)
        weighings = weighings.order_by('-date_time')
        if not weighings:
            return 0
        return weighings[0].weight

    def expected_weighing_mean_std(self, age_w):
        sex = 'male' if self.sex == 'M' else 'female'
        path = op.join(op.dirname(__file__),
                       'static/ref_weighings_%s.csv' % sex)
        with open(path, 'r') as f:
            reader = csv.reader(f)
            d = {int(age): (float(m), float(s))
                 for age, m, s in list(reader)}
        age_min, age_max = min(d), max(d)
        if age_w < age_min:
            return d[age_min]
        elif age_w > age_max:
            return d[age_max]
        else:
            return d[age_w]

    def water_requirement_total(self):
        # returns the amount of water the subject needs today in total

        rw = self.reference_weighing()
        cw = self.current_weighing()

        start_weight = rw.weight
        implant_weight = self.implant_weight or 0

        if not self.birth_date:
            logger.warn("Subject %s has no birth date!", self)
            return 0
        start_age = (rw.date_time.date() - self.birth_date).days // 7

        today_weight = cw.weight
        today_age = self.age_days() // 7  # in weeks

        start_mrw, start_srw = self.expected_weighing_mean_std(start_age)
        today_mrw, today_srw = self.expected_weighing_mean_std(today_age)

        subj_zscore = (start_weight - implant_weight - start_mrw) / start_srw

        expected_weight_today = (today_srw * subj_zscore) + \
            today_mrw + implant_weight
        thresh_weight = 0.8 * expected_weight_today

        if today_weight < thresh_weight:
            return 0.05 * today_weight
        else:
            return 0.04 * today_weight

    def water_requirement_remaining(self):
        # returns the amount of water the subject still needs, given how much
        # it got already today

        req_total = self.water_requirement_total()

        today = timezone.now()
        water_today = WaterAdministration.objects.filter(subject__id=self.id,
                                                         date_time__date=today)

        # extract the amounts of all water_today, sum them, subtract from
        # req_total
        water_today = water_today.aggregate(models.Sum('water_administered'))
        return req_total - (water_today['water_administered__sum'] or 0)

    def zygosity_strings(self):
        return (str(z) for z in Zygosity.objects.filter(subject__id=self.id))

    def save(self, *args, **kwargs):
        # When a subject dies, remove it from a cage.
        if not self.alive() and self.cage is not None:
            self.cage = None
        if self.line and self.nickname in (None, '', '-'):
            self.line.set_autoname(self)
        return super(Subject, self).save(*args, **kwargs)

    def __str__(self):
        return self.nickname


class SubjectRequest(BaseModel):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='subjects_requested',
                             help_text="Who requested this subject.")
    line = models.ForeignKey('Line', null=True, blank=True, on_delete=models.SET_NULL)
    count = models.IntegerField(null=True, blank=True)
    date_time = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_time']

    def status(self):
        return 'Open' if self.remaining() > 0 else 'Closed'

    def remaining(self):
        return (self.count or 0) - len(self.subjects())

    def subjects(self):
        return Subject.objects.filter(responsible_user=self.user,
                                      line=self.line,
                                      death_date__isnull=True,
                                      request=self,
                                      )

    def __str__(self):
        return '{count} {line} due {due_date} for {user}'.format(
            count=self.count, line=self.line, due_date=self.due_date, user=self.user,
        )


@receiver(post_save, sender=SubjectRequest)
def send_subject_request_mail_new(sender, instance=None, **kwargs):
    """Send en email when a subject request is created."""
    if not instance or not kwargs['created']:
        return
    subject = "[alyx] %s requested: %s" % (instance.user, str(instance))
    body = ''
    try:
        send_mail(subject, body, settings.SUBJECT_REQUEST_EMAIL_FROM,
                  [settings.SUBJECT_REQUEST_EMAIL_TO],
                  fail_silently=True,
                  )
        logger.debug("Mail sent.")
    except Exception as e:
        logger.warn("Mail failed: %s", e)


@receiver(post_save, sender=Subject)
def send_subject_request_mail_change(sender, instance=None, **kwargs):
    """Send en email when a subject's request changes."""
    if not instance:
        return
    # Only continue if the request has changed.
    if not (instance._original_request is None and instance.request is not None):
        return
    # Only continue if there's an email.
    if not instance.responsible_user.email:
        return
    subject = ("[alyx] Subject %s was assigned to you for request %s" %
               (instance.nickname, str(instance.request)))
    body = ''
    try:
        send_mail(subject, body, settings.SUBJECT_REQUEST_EMAIL_FROM,
                  [instance.responsible_user.email],
                  fail_silently=True,
                  )
        logger.debug("Mail sent.")
    except Exception as e:
        logger.warn("Mail failed: %s", e)


class Litter(BaseModel):
    """A litter, containing a mother, father, and children with a
    shared date of birth."""
    descriptive_name = models.CharField(max_length=255, default='-')
    mother = models.ForeignKey('Subject', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               limit_choices_to={'sex': 'F'},
                               related_name="litter_mother")
    father = models.ForeignKey('Subject', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               limit_choices_to={'sex': 'M'},
                               related_name="litter_father")
    line = models.ForeignKey('Line', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    cage = models.ForeignKey('Cage', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    notes = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-birth_date']

    def save(self, *args, **kwargs):
        if self.line and self.descriptive_name in (None, '', '-'):
            self.line.set_autoname(self)
        return super(Litter, self).save(*args, **kwargs)

    def __str__(self):
        return self.descriptive_name


class Cage(BaseModel):
    CAGE_TYPES = (
        ('I', 'IVC'),
        ('R', 'Regular'),
    )

    cage_label = models.CharField(max_length=255, default='-',
                                  help_text='Leave to "-" to autofill.')
    type = models.CharField(max_length=1, choices=CAGE_TYPES, default='I',
                            help_text="Is this an IVC or regular cage?")
    line = models.ForeignKey('Line', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    location = models.ForeignKey(LabLocation)

    class Meta:
        ordering = ['cage_label']

    def save(self, *args, **kwargs):
        if self.line and self.cage_label in (None, '', '-'):
            self.line.set_autoname(self)
        return super(Cage, self).save(*args, **kwargs)

    def __str__(self):
        return self.cage_label


class Line(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_phenotype = models.CharField(max_length=1023)
    auto_name = models.CharField(max_length=255)
    sequences = models.ManyToManyField('Sequence')
    strain = models.ForeignKey('Strain', null=True, blank=True, on_delete=models.SET_NULL)
    species = models.ForeignKey('Species', null=True, blank=True, on_delete=models.SET_NULL,
                                default=MOUSE_SPECIES_ID)
    subject_autoname_index = models.IntegerField(default=0)
    cage_autoname_index = models.IntegerField(default=0)
    litter_autoname_index = models.IntegerField(default=0)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def new_cage_autoname(self):
        self.cage_autoname_index = self.cage_autoname_index + 1
        self.save()
        return '%s_C_%d' % (self.auto_name, self.cage_autoname_index)

    def new_litter_autoname(self):
        self.litter_autoname_index = self.litter_autoname_index + 1
        self.save()
        return '%s_L_%d' % (self.auto_name, self.litter_autoname_index)

    def new_subject_autoname(self):
        self.subject_autoname_index = self.subject_autoname_index + 1
        self.save()
        return '%s_%d' % (self.auto_name, self.subject_autoname_index)

    def set_autoname(self, obj):
        if isinstance(obj, Cage):
            field = 'cage_label'
            m = self.new_cage_autoname
        elif isinstance(obj, Litter):
            field = 'descriptive_name'
            m = self.new_litter_autoname
        elif isinstance(obj, Subject):
            field = 'nickname'
            m = self.new_subject_autoname
        if getattr(obj, field, None) in (None, '-'):
            setattr(obj, field, m())


class Strain(BaseModel):
    """A strain with a standardised name. """
    descriptive_name = models.CharField(max_length=255,
                                        help_text="Standard descriptive name E.g. \"C57BL/6J\", "
                                        "http://www.informatics.jax.org/mgihome/nomen/")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['descriptive_name']

    def __str__(self):
        return self.descriptive_name


class Allele(BaseModel):
    """A single allele."""
    standard_name = models.CharField(max_length=1023,
                                     help_text="MGNC-standard genotype name e.g. "
                                     "Pvalb<tm1(cre)Arbr>, "
                                     "http://www.informatics.jax.org/mgihome/nomen/")
    informal_name = models.CharField(max_length=255,
                                     help_text="informal name in lab, e.g. Pvalb-Cre")

    class Meta:
        ordering = ['standard_name']

    def __str__(self):
        return self.informal_name


class Zygosity(BaseModel):
    """
    A junction table between Subject and Allele.
    """
    ZYGOSITY_TYPES = (
        (0, 'Absent'),
        (1, 'Heterozygous'),
        (2, 'Homozygous'),
        (3, 'Present'),
    )
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    allele = models.ForeignKey('Allele', on_delete=models.CASCADE)
    zygosity = models.IntegerField(choices=ZYGOSITY_TYPES)

    def __str__(self):
        symbol = ('-/-', '+/-', '+/+', '+')[self.zygosity] if self.zygosity is not None else '?'
        return "{0:s} {1:s}".format(str(self.allele), symbol)

    class Meta:
        verbose_name_plural = "zygosities"


class Sequence(BaseModel):
    """A genetic sequence that you run a genotyping test for."""
    base_pairs = models.TextField(
        help_text="the actual sequence of base pairs in the test")
    description = models.CharField(max_length=1023,
                                   help_text="any other relevant information about this test")
    informal_name = models.CharField(max_length=255,
                                     help_text="informal name in lab, e.g. ROSA-WT")

    class Meta:
        ordering = ['informal_name']

    def __str__(self):
        return self.informal_name


class GenotypeTest(BaseModel):
    TEST_RESULTS = (
        (0, 'Absent'),
        (1, 'Present'),
    )
    """
    A junction table between Subject and Sequence.
    """
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    sequence = models.ForeignKey('Sequence', on_delete=models.CASCADE)
    test_result = models.IntegerField(choices=TEST_RESULTS)

    class Meta:
        verbose_name_plural = "genotype tests"

    def __str__(self):
        return "%s %s" % (self.sequence, '-+'[self.test_result])


class Source(BaseModel):
    """A supplier / source of subjects."""
    name = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Species(BaseModel):
    """A single species, identified uniquely by its binomial name."""
    binomial = models.CharField(max_length=255,
                                help_text="Binomial name, "
                                "e.g. \"mus musculus\"")
    display_name = models.CharField(max_length=255,
                                    help_text="common name, e.g. \"mouse\"")

    class Meta:
        ordering = ['display_name']
        verbose_name_plural = "species"

    def __str__(self):
        return self.display_name
