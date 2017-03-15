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

from .zygosities import ZYGOSITY_RULES
from alyx.base import BaseModel
from equipment.models import LabLocation
from actions.models import WaterRestriction, Weighing, WaterAdministration

logger = logging.getLogger(__name__)


MOUSE_SPECIES_ID = 'c8339f4f-4afe-49d5-b2a2-a7fc61389aaf'
DEFAULT_RESPONSIBLE_USER_ID = 5


# Subject
# ------------------------------------------------------------------------------------------------

class SubjectManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(nickname=name)


class Subject(BaseModel):
    """Metadata about an experimental subject (animal or human)."""
    SEXES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('U', 'Unknown')
    )
    SEVERITY_CHOICES = (
        (None, ''),
        (1, 'Sub-threshold'),
        (2, 'Mild'),
        (3, 'Moderate'),
        (4, 'Severe'),
        (5, 'Non-recovery'),
    )
    PROTOCOL_NUMBERS = tuple((str(i), str(i)) for i in range(1, 5))

    nickname = models.CharField(max_length=255,
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
    lamis_cage = models.IntegerField(null=True, blank=True)
    request = models.ForeignKey('SubjectRequest', null=True, blank=True,
                                on_delete=models.SET_NULL)
    implant_weight = models.FloatField(null=True, blank=True, help_text="Implant weight in grams")
    ear_mark = models.CharField(max_length=32, blank=True)
    protocol_number = models.CharField(max_length=1, choices=PROTOCOL_NUMBERS, default='3')
    notes = models.TextField(blank=True)

    cull_method = models.TextField(blank=True)
    adverse_effects = models.TextField(blank=True)
    actual_severity = models.IntegerField(null=True, blank=True, choices=SEVERITY_CHOICES)

    to_be_genotyped = models.BooleanField(default=False)
    to_be_culled = models.BooleanField(default=False)
    reduced = models.BooleanField(default=False)

    objects = SubjectManager()

    def natural_key(self):
        return (self.nickname,)

    class Meta:
        ordering = ['-nickname', '-birth_date']

    def __init__(self, *args, **kwargs):
        super(Subject, self).__init__(*args, **kwargs)
        # Used to detect when the request has changed.
        self._original_request = self.request
        self._original_litter = self.litter
        self._original_genotype_date = self.genotype_date

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
            return self.litter.breeding_pair.mother1

    def father(self):
        if self.litter:
            return self.litter.breeding_pair.father

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
            return None
        return weighings[0]

    def current_weighing(self):
        weighings = Weighing.objects.filter(subject__id=self.id)
        weighings = weighings.order_by('-date_time')
        if not weighings:
            return None
        return weighings[0]

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

    def genotype_test_string(self):
        tests = GenotypeTest.objects.filter(subject=self).order_by('sequence__informal_name')
        return ','.join('%s%s' % ('-' if test.test_result == 0 else '', str(test.sequence))
                        for test in tests)

    def save(self, *args, **kwargs):
        # If the nickname is empty, use the autoname from the line.
        if self.line and self.nickname in (None, '', '-'):
            self.line.set_autoname(self)
        # Default strain.
        if self.line and not self.strain:
            self.strain = self.line.strain
        # Update the zygosities when the subject is assigned a litter.
        if self.litter and not self._original_litter:
            ZygosityFinder().genotype_from_litter(self)
        # Remove "to be genotyped" if genotype date is set.
        if self.genotype_date and not self._original_genotype_date:
            self.to_be_genotyped = False
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


# Other
# ------------------------------------------------------------------------------------------------

class LitterManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(descriptive_name=name)


class Litter(BaseModel):
    """A litter, containing a mother, father, and children with a
    shared date of birth."""
    descriptive_name = models.CharField(max_length=255, default='-')
    line = models.ForeignKey('Line', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    breeding_pair = models.ForeignKey('BreedingPair', null=True, blank=True,
                                      on_delete=models.SET_NULL,
                                      )
    notes = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)

    objects = LitterManager()

    def natural_key(self):
        return (self.descriptive_name,)

    class Meta:
        ordering = ['descriptive_name', '-birth_date']

    def save(self, *args, **kwargs):
        if self.line and self.descriptive_name in (None, '', '-'):
            self.line.set_autoname(self)
        return super(Litter, self).save(*args, **kwargs)

    def __str__(self):
        return self.descriptive_name


class BreedingPairManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class BreedingPair(BaseModel):
    name = models.CharField(max_length=255, default='-',
                            help_text='Leave to "-" to autofill.')
    line = models.ForeignKey('Line', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    father = models.ForeignKey('Subject', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               limit_choices_to={'sex': 'M'},
                               related_name="litter_father")
    mother1 = models.ForeignKey('Subject', null=True, blank=True,
                                on_delete=models.SET_NULL,
                                limit_choices_to={'sex': 'F'},
                                related_name="mother1")
    mother2 = models.ForeignKey('Subject', null=True, blank=True,
                                on_delete=models.SET_NULL,
                                limit_choices_to={'sex': 'F'},
                                related_name="mother2")
    notes = models.TextField(blank=True)

    objects = BreedingPairManager()

    def natural_key(self):
        return (self.name,)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Breeding pairs'

    def save(self, *args, **kwargs):
        if self.line and self.name in (None, '', '-'):
            self.line.set_autoname(self)
        return super(BreedingPair, self).save(*args, **kwargs)

    def __str__(self):
        return self.name


class LineManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(auto_name=name)


class Line(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_phenotype = models.CharField(max_length=1023)
    auto_name = models.CharField(max_length=255, unique=True)
    sequences = models.ManyToManyField('Sequence')
    strain = models.ForeignKey('Strain', null=True, blank=True, on_delete=models.SET_NULL)
    species = models.ForeignKey('Species', null=True, blank=True, on_delete=models.SET_NULL,
                                default=MOUSE_SPECIES_ID)
    subject_autoname_index = models.IntegerField(default=0)
    breeding_pair_autoname_index = models.IntegerField(default=0)
    litter_autoname_index = models.IntegerField(default=0)

    objects = LineManager()

    def natural_key(self):
        return (self.auto_name,)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def new_breeding_pair_autoname(self):
        self.breeding_pair_autoname_index = self.breeding_pair_autoname_index + 1
        self.save()
        return '%s_BP_%03d' % (self.auto_name, self.breeding_pair_autoname_index)

    def new_litter_autoname(self):
        self.litter_autoname_index = self.litter_autoname_index + 1
        self.save()
        return '%s_L_%03d' % (self.auto_name, self.litter_autoname_index)

    def new_subject_autoname(self):
        self.subject_autoname_index = self.subject_autoname_index + 1
        self.save()
        return '%s_%04d' % (self.auto_name, self.subject_autoname_index)

    def set_autoname(self, obj):
        if isinstance(obj, BreedingPair):
            field = 'name'
            m = self.new_breeding_pair_autoname
        elif isinstance(obj, Litter):
            field = 'descriptive_name'
            m = self.new_litter_autoname
        elif isinstance(obj, Subject):
            field = 'nickname'
            m = self.new_subject_autoname
        if getattr(obj, field, None) in (None, '-'):
            setattr(obj, field, m())


class SpeciesManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(display_name=name)


class Species(BaseModel):
    """A single species, identified uniquely by its binomial name."""
    binomial = models.CharField(max_length=255,
                                help_text="Binomial name, "
                                "e.g. \"mus musculus\"")
    display_name = models.CharField(max_length=255, unique=True,
                                    help_text="common name, e.g. \"mouse\"")

    objects = SpeciesManager()

    def natural_key(self):
        return (self.display_name,)

    def __str__(self):
        return self.display_name

    class Meta:
        verbose_name_plural = "species"


class StrainManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(descriptive_name=name)


class Strain(BaseModel):
    """A strain with a standardised name. """
    descriptive_name = models.CharField(max_length=255, unique=True,
                                        help_text="Standard descriptive name E.g. \"C57BL/6J\", "
                                        "http://www.informatics.jax.org/mgihome/nomen/")
    description = models.TextField(blank=True)

    objects = StrainManager()

    def natural_key(self):
        return (self.descriptive_name,)

    class Meta:
        ordering = ['descriptive_name']

    def __str__(self):
        return self.descriptive_name


class Source(BaseModel):
    """A supplier / source of subjects."""
    name = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


# Genotypes
# ------------------------------------------------------------------------------------------------

class ZygosityFinder(object):
    def _existing_alleles(self, subject):
        if not subject:
            return []
        return set([allele.informal_name for allele in subject.genotype.all()])

    def _alleles_in_line(self, line):
        for l, allele, _ in ZYGOSITY_RULES:
            if line and l == line.auto_name:
                yield allele

    def _parse_rule(self, rule):
        string, res = rule
        out = {}
        for substr in string.split(','):
            if substr[0] == '-':
                sign = 0
                substr = substr[1:]
            else:
                sign = 1
            out[substr] = sign
        out['res'] = res
        return out

    def _find_zygosity(self, rules, tests):
        if not tests:
            return
        tests = {test.sequence.informal_name: test.test_result for test in tests}
        for rule in rules:
            d = self._parse_rule(rule)
            match = all(tests.get(test, None) == res for test, res in d.items() if test != 'res')
            if match:
                return d['res']

    def _get_allele_rules(self, line, allele):
        for l, a, rules in ZYGOSITY_RULES:
            if l == line and a == allele:
                return rules
        return []

    def _get_tests(self, subject):
        return GenotypeTest.objects.filter(subject=subject)

    def _get_allele(self, name):
        return Allele.objects.get_or_create(informal_name=name)[0]

    def _create_zygosity(self, subject, allele_name, symbol):
        if symbol is not None:
            zygosity = Zygosity.objects.filter(subject=subject,
                                               allele=self._get_allele(allele_name),
                                               )
            z = Zygosity.from_symbol(symbol)
            # Get or create the zygosity.
            if zygosity:
                zygosity = zygosity[0]
                zygosity.zygosity = z
            else:
                zygosity = Zygosity(subject=subject,
                                    allele=self._get_allele(allele_name),
                                    zygosity=z,
                                    )
            zygosity.save()

    def update_subject(self, subject):
        if not subject.line:
            return
        line = subject.line.auto_name
        alleles_in_line = set(self._alleles_in_line(subject.line))
        tests = self._get_tests(subject)
        for allele in alleles_in_line:
            rules = self._get_allele_rules(line, allele)
            z = self._find_zygosity(rules, tests)
            self._create_zygosity(subject, allele, z)

    def _get_parents_alleles(self, subject, allele):
        out = {'mother': None, 'father': None}
        for which_parent in ('mother', 'father'):
            parent = getattr(subject, which_parent)()
            if parent is not None:
                zygosities = Zygosity.objects.filter(subject=parent,
                                                     allele__informal_name=allele,
                                                     )
                if zygosities:
                    z = zygosities[0]
                    out[which_parent] = z.symbol()
        return out['mother'], out['father']

    def _zygosity_from_parents(self, subject, allele):
        zm, zf = self._get_parents_alleles(subject, allele)
        if zm == '+/+' and zf == '+/+':
            return '+/+'
        elif zm and zf and '+/+' in (zm, zf):
            return '+'
        elif zm and zf and '-/-' in (zm, zf):
            return '-/-'
        elif '+/+' in (zm, zf) and None in (zm, zf):
            return '+/-'
        elif '-/-' in (zm, zf) and None in (zm, zf):
            return '-/-'
        else:
            return None

    def genotype_from_litter(self, subject):
        if not subject.litter:
            return
        bp = subject.litter.breeding_pair
        if not bp:
            return
        mother = bp.mother1
        father = bp.father
        alleles_m = self._existing_alleles(mother)
        alleles_f = self._existing_alleles(father)
        alleles = set(alleles_m).union(set(alleles_f))
        for allele in alleles:
            z = self._zygosity_from_parents(subject, allele)
            self._create_zygosity(subject, allele, z)


class AlleleManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(informal_name=name)


class Allele(BaseModel):
    """A single allele."""
    standard_name = models.CharField(max_length=1023,
                                     help_text="MGNC-standard genotype name e.g. "
                                     "Pvalb<tm1(cre)Arbr>, "
                                     "http://www.informatics.jax.org/mgihome/nomen/")
    informal_name = models.CharField(max_length=255, unique=True,
                                     help_text="informal name in lab, e.g. Pvalb-Cre")

    objects = AlleleManager()

    def natural_key(self):
        return (self.informal_name,)

    class Meta:
        ordering = ['informal_name']

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
    ZYGOSITY_SYMBOLS = ('-/-', '+/-', '+/+', '+')

    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    allele = models.ForeignKey('Allele', on_delete=models.CASCADE)
    zygosity = models.IntegerField(choices=ZYGOSITY_TYPES)

    @staticmethod
    def from_symbol(symbol):
        return Zygosity.ZYGOSITY_SYMBOLS.index(symbol)

    def symbol(self):
        return (self.ZYGOSITY_SYMBOLS[self.zygosity]
                if self.zygosity is not None else '?')

    def __str__(self):
        return "{0:s} {1:s}".format(str(self.allele), self.symbol())

    class Meta:
        verbose_name_plural = "zygosities"


class SequenceManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(informal_name=name)


class Sequence(BaseModel):
    """A genetic sequence that you run a genotyping test for."""
    base_pairs = models.TextField(
        help_text="the actual sequence of base pairs in the test")
    description = models.CharField(max_length=1023,
                                   help_text="any other relevant information about this test")
    informal_name = models.CharField(max_length=255, unique=True,
                                     help_text="informal name in lab, e.g. ROSA-WT")

    objects = SequenceManager()

    def natural_key(self):
        return (self.informal_name,)

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

    def save(self, *args, **kwargs):
        super(GenotypeTest, self).save(*args, **kwargs)
        # First, save, then update the subject's zygosities.
        ZygosityFinder().update_subject(self.subject)
