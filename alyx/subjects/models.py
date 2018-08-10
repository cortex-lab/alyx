from datetime import datetime
import logging
import urllib

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core import validators
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from alyx.base import BaseModel, alyx_mail
from actions.models import WaterRestriction
from actions.water import last_water_restriction, today
from misc.models import Lab

logger = logging.getLogger(__name__)


# Zygosity constants
# ------------------------------------------------------------------------------------------------

ZYGOSITY_TYPES = (
    (0, 'Absent'),
    (1, 'Heterozygous'),
    (2, 'Homozygous'),
    (3, 'Present'),
)

ZYGOSITY_SYMBOLS = ('-/-', '+/-', '+/+', '+')

TEST_RESULTS = (
    (0, 'Absent'),
    (1, 'Present'),
)


# Subject
# ------------------------------------------------------------------------------------------------

def _is_foreign_key(obj, field):
    return hasattr(obj, field + '_id')


def _get_current_field(obj, field):
    if _is_foreign_key(obj, field):
        return getattr(obj, field + '_id', None)
    else:
        return str(getattr(obj, field, None))


def init_old_fields(obj, fields):
    obj._original_fields = getattr(obj, '_original_fields', {})
    for field in fields:
        obj._original_fields[field] = _get_current_field(obj, field)


def save_old_fields(obj, fields):
    date_time = datetime.now(timezone.utc).isoformat()
    d = (getattr(obj, 'json', None) or {}).get('history', {})
    for field in fields:
        v = _get_current_field(obj, field)
        if v is None or v == obj._original_fields.get(field, None):
            continue
        if field not in d:
            d[field] = []
        l = d[field]
        l.append({'date_time': date_time, 'value': obj._original_fields[field]})
        # Update the new value.
        # obj._original_fields[field] = v
        # Set the object's JSON if necessary.
        if not obj.json:
            obj.json = {}
        if 'history' not in obj.json:
            obj.json['history'] = {}
        obj.json['history'].update(d)


def _get_old_field(obj, field):
    return obj._original_fields.get(field, None)


def _has_field_changed(obj, field):
    current = _get_current_field(obj, field)
    original = _get_old_field(obj, field)
    return current != original


class SubjectManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(nickname=name)


def _default_source():
    s = Source.objects.filter(name=settings.DEFAULT_SOURCE)
    if s:
        return s[0]
    return None


def default_responsible():
    return get_user_model().objects.filter(is_stock_manager=True).first()


def default_species():
    return Species.objects.get_or_create(
        display_name='Laboratory mouse', binomial="Mus musculus")[0].pk


class Project(BaseModel):
    name = models.CharField(
        max_length=255, unique=True, blank=True, help_text="Project name")

    description = models.CharField(
        max_length=1023, blank=True, help_text="Description of the project")

    repositories = models.ManyToManyField(
        'data.DataRepository', blank=True,
        help_text="Related DataRepository instances. Any file which is registered to Alyx is "
        "automatically copied to all repositories assigned to its project.")

    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        help_text="Persons associated to the project.")

    def __str__(self):
        return "<Project %s>" % self.name


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

    nickname_validator = validators.RegexValidator(r'^[-._~\w]+$',
                                                   "Nicknames must only contain letters, "
                                                   "numbers, or any of -._~.")

    nickname = models.CharField(max_length=255,
                                default='-',
                                help_text="Easy-to-remember, unique name "
                                          "(e.g. 'Hercules').",
                                validators=[nickname_validator])
    species = models.ForeignKey('Species', null=True, blank=True, on_delete=models.SET_NULL,
                                default=default_species)
    litter = models.ForeignKey('Litter', null=True, blank=True, on_delete=models.SET_NULL)
    sex = models.CharField(max_length=1, choices=SEXES,
                           blank=True, default='U')
    strain = models.ForeignKey('Strain', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               )
    genotype = models.ManyToManyField('Allele', through='Zygosity')
    genotype_test = models.ManyToManyField('Sequence', through='GenotypeTest')
    source = models.ForeignKey('Source', null=True, blank=True, on_delete=models.SET_NULL,
                               default=_default_source)
    line = models.ForeignKey('Line', null=True, blank=True, on_delete=models.SET_NULL)
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)
    wean_date = models.DateField(null=True, blank=True)
    genotype_date = models.DateField(null=True, blank=True)
    responsible_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                         on_delete=models.SET_NULL,
                                         default=default_responsible,
                                         related_name='subjects_responsible',
                                         help_text="Who has primary or legal responsibility "
                                         "for the subject.")
    lab = models.ForeignKey(Lab, null=True, blank=True, on_delete=models.SET_NULL)

    projects = models.ManyToManyField(
        Project, blank=True,
        help_text='Project associated to this session')

    lamis_cage = models.IntegerField(null=True, blank=True)
    request = models.ForeignKey('SubjectRequest', null=True, blank=True,
                                on_delete=models.SET_NULL)
    implant_weight = models.FloatField(null=True, blank=True, help_text="Implant weight in grams")
    ear_mark = models.CharField(max_length=32, blank=True)
    protocol_number = models.CharField(max_length=1, choices=PROTOCOL_NUMBERS,
                                       default=settings.DEFAULT_PROTOCOL)
    description = models.TextField(blank=True)

    cull_method = models.TextField(blank=True)
    adverse_effects = models.TextField(blank=True)
    actual_severity = models.IntegerField(null=True, blank=True, choices=SEVERITY_CHOICES)

    to_be_genotyped = models.BooleanField(default=False)
    to_be_culled = models.BooleanField(default=False)
    reduced = models.BooleanField(default=False)
    reduced_date = models.DateField(null=True, blank=True)

    objects = SubjectManager()

    # We save the history of these fields.
    _fields_history = ('nickname', 'responsible_user', 'lamis_cage')
    # We track the changes of these fields without saving their history in the JSON.
    _track_field_changes = ('request', 'litter', 'genotype_date', 'death_date', 'reduced')

    class Meta:
        ordering = ['nickname', '-birth_date']

    def __init__(self, *args, **kwargs):
        super(Subject, self).__init__(*args, **kwargs)
        # Initialize the history of some fields.
        init_old_fields(self, self._fields_history + self._track_field_changes)

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

    def last_water_restriction(self):
        return last_water_restriction(self, today())

    def zygosity_strings(self):
        alleles = self.line.alleles.all() if self.line else Allele.objects.all()
        return list(map(str, self.zygosity_set.filter(allele__in=alleles)))

    def is_negative(self):
        """Genotype is -/- for all genes."""
        return all(z.zygosity == 0 for z in Zygosity.objects.filter(subject=self))

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
        # Update the zygosities when the subject is created or assigned a litter.
        is_created = self._state.adding is True
        if is_created or (self.litter_id and not _get_old_field(self, 'litter')):
            ZygosityFinder().genotype_from_litter(self)
        # Remove "to be genotyped" if genotype date is set.
        if self.genotype_date and not _get_old_field(self, 'genotype_date'):
            self.to_be_genotyped = False
        # When a subject dies.
        if self.death_date and not _get_old_field(self, 'death_date'):
            # Close all water restrictions without an end date.
            for wr in WaterRestriction.objects.filter(subject=self,
                                                      start_time__isnull=False,
                                                      end_time__isnull=True):
                wr.end_time = self.death_date
                wr.save()
        # Save the reduced date.
        if self.reduced and _has_field_changed(self, 'reduced'):
            self.reduced_date = timezone.now().date()
        # Update subject request.
        if (self.responsible_user_id and _has_field_changed(self, 'responsible_user') and
                self.line is not None and
                self.request is None):
            srs = SubjectRequest.objects.filter(user=self.responsible_user,
                                                line=self.line)
            if srs:
                self.request = srs[0]
        # Keep the history of some fields in the JSON.
        save_old_fields(self, self._fields_history)
        return super(Subject, self).save(*args, **kwargs)

    def __str__(self):
        return self.nickname


class SubjectRequest(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='subjects_requested',
        help_text="Who requested this subject.")
    line = models.ForeignKey('Line', null=True, blank=True, on_delete=models.SET_NULL)
    count = models.IntegerField(null=True, blank=True)
    date_time = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_time']

    def status(self):
        return 'Open' if self.remaining() > 0 else 'Closed'

    def remaining(self):
        return (self.count or 0) - len(self.subjects())

    def subjects(self):
        subjects = self.subject_set.all()
        return [s for s in subjects
                if s.responsible_user_id == self.user_id and
                s.line_id == self.line_id and s.death_date is None]

    def __str__(self):
        return '{count} {line} due {due_date} for {user}'.format(
            count=self.count, line=self.line, due_date=self.due_date, user=self.user,
        )


@receiver(post_save, sender=SubjectRequest)
def send_subject_request_mail_new(sender, instance=None, **kwargs):
    """Send en email when a subject request is created."""
    if not instance or not kwargs['created']:
        return
    subject = "%s requested: %s" % (instance.user, str(instance))
    to = [sm.email for sm in get_user_model().objects.filter(
          is_stock_manager=True, email__isnull=False)]
    alyx_mail(to, subject, instance.description)


@receiver(post_save, sender=Subject)
def send_subject_request_mail_change(sender, instance=None, **kwargs):
    """Send en email when a subject's request changes."""
    if not instance:
        return
    # Only continue if the request has changed.
    if not (_get_current_field(instance, 'request') is not None and
            _get_old_field(instance, 'request') is None):
        return
    # Only continue if there's an email.
    if not instance.responsible_user.email:
        return
    subject = ("Subject %s was assigned to you for request %s" %
               (instance.nickname, str(instance.request)))
    alyx_mail(instance.responsible_user.email, subject)


@receiver(post_save, sender=Subject)
def send_subject_responsible_user_mail_change(sender, instance=None, **kwargs):
    """Send en email when a subject's responsible user changes."""
    if not instance:
        return
    # Only continue if the request has changed.
    if not _has_field_changed(instance, 'responsible_user'):
        return
    # Only continue if there's an email.
    if not instance.responsible_user.email:
        return
    logger.info("Subject %s was assigned from %s to %s.",
                instance,
                _get_old_field(instance, 'responsible_user'),
                instance.responsible_user,
                )
    subject = "Subject %s was assigned to you" % instance.nickname
    alyx_mail(instance.responsible_user.email, subject)


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
    description = models.TextField(blank=True)
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
    description = models.TextField(blank=True)

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
    alleles = models.ManyToManyField('Allele')
    strain = models.ForeignKey('Strain', null=True, blank=True, on_delete=models.SET_NULL)
    source = models.ForeignKey('Source', null=True, blank=True, on_delete=models.SET_NULL)
    source_identifier = models.CharField(max_length=64, blank=True)
    source_url = models.URLField(blank=True)
    expression_data_url = models.URLField(blank=True)
    species = models.ForeignKey('Species', null=True, blank=True, on_delete=models.SET_NULL,
                                default=default_species)
    subject_autoname_index = models.IntegerField(default=0)
    breeding_pair_autoname_index = models.IntegerField(default=0)
    litter_autoname_index = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    objects = LineManager()

    def natural_key(self):
        return (self.auto_name,)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.auto_name

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


class SourceManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Source(BaseModel):
    """A supplier / source of subjects."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    objects = SourceManager

    def __str__(self):
        return self.name


# Genotypes
# ------------------------------------------------------------------------------------------------

def _update_zygosyties(line, sequence):
    # Apply the rule.
    zf = ZygosityFinder()
    # Subjects from the line and that have a test with the first sequence.
    subjects = set(gt.subject for gt in GenotypeTest.objects.filter(
        sequence=sequence,
        subject__line=line))
    for subject in subjects:
        # Note: need force=True when deleting a zygosity rule.
        zf.genotype_from_litter(subject, force=True)
        zf.update_subject(subject)


class ZygosityRule(BaseModel):
    line = models.ForeignKey('Line', null=True, on_delete=models.SET_NULL)
    allele = models.ForeignKey('Allele', null=True, on_delete=models.SET_NULL)
    sequence0 = models.ForeignKey('Sequence', blank=True, null=True, on_delete=models.SET_NULL,
                                  related_name='zygosity_rule_sequence0')
    sequence0_result = models.IntegerField(choices=TEST_RESULTS, null=True, blank=True)
    sequence1 = models.ForeignKey('Sequence', blank=True, null=True, on_delete=models.SET_NULL,
                                  related_name='zygosity_rule_sequence1')
    sequence1_result = models.IntegerField(choices=TEST_RESULTS, null=True, blank=True)
    zygosity = models.IntegerField(choices=ZYGOSITY_TYPES)

    def save(self, *args, **kwargs):
        super(ZygosityRule, self).save(*args, **kwargs)
        _update_zygosyties(self.line, self.sequence0)

    def __str__(self):
        return '<Rule {line} {allele}: {seq0} {res0}, {seq1} {res1} => {z}>'.format(
            line=self.line, allele=self.allele,
            seq0=self.sequence0, res0=self.sequence0_result,
            seq1=self.sequence1, res1=self.sequence1_result, z=self.zygosity
        )


class ZygosityFinder(object):
    def _existing_alleles(self, subject):
        if not subject:
            return []
        return set([allele.informal_name for allele in subject.genotype.all()])

    def _alleles_in_line(self, line):
        return (zr.allele for zr in ZygosityRule.objects.filter(line=line))

    def _find_zygosity(self, rules, tests):
        if not tests:
            return
        tests = {test.sequence: test.test_result for test in tests}
        for rule in rules:
            result0 = tests.get(rule.sequence0, None)
            result1 = tests.get(rule.sequence1, None)
            pass0 = rule.sequence0_result == result0
            pass1 = rule.sequence1_result == result1
            if (result1 is None and pass0) or (result1 is not None and pass0 and pass1):
                return rule.zygosity

    def _get_allele_rules(self, line, allele):
        return ZygosityRule.objects.filter(line__auto_name=line, allele__informal_name=allele)

    def _get_tests(self, subject):
        return GenotypeTest.objects.filter(subject=subject)

    def _get_allele(self, name):
        return Allele.objects.get_or_create(informal_name=name)[0]

    def _create_zygosity(self, subject, allele_name, symbol, force=True):
        if symbol is not None:
            zygosity = Zygosity.objects.filter(subject=subject,
                                               allele=self._get_allele(allele_name),
                                               )
            z = Zygosity.from_symbol(symbol)
            # Get or create the zygosity.
            if zygosity:
                zygosity = zygosity[0]
                if z != zygosity.zygosity:
                    if force:
                        logger.warn("Zygosity mismatch for %s: was %s, now set to %s.",
                                    subject, zygosity, symbol)
                    else:
                        logger.warn("Zygosity mismatch for %s: was %s, would have been set "
                                    "to %s but aborting now.", subject, zygosity, symbol)
                        return
                zygosity.zygosity = z
            else:
                zygosity = Zygosity(subject=subject,
                                    allele=self._get_allele(allele_name),
                                    zygosity=z,
                                    )
            zygosity.save()

    def update_subject(self, subject, force=True):
        if not subject.line:
            return
        logger.debug("Genotype from rules for subject %s", subject.nickname)
        line = subject.line.auto_name
        alleles_in_line = set(self._alleles_in_line(subject.line))
        tests = self._get_tests(subject)
        for allele in alleles_in_line:
            rules = self._get_allele_rules(line, allele)
            z = self._find_zygosity(rules, tests)
            if z is None:
                continue
            symbol = ZYGOSITY_SYMBOLS[z]
            logger.debug("Zygosity %s: %s %s from tests %s.",
                         subject, allele, symbol, ', '.join(str(_) for _ in tests))
            self._create_zygosity(subject, allele, symbol, force=force)

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

    def _zygosity_from_parents(self, zm, zf):
        return {
            ('+/+', '+/+'): '+/+',
            ('+/+', '+/-'): '+',
            ('+/+', '-/-'): '+/-',
            ('+/+', '+'): '+',
            ('+/+', None): '+/-',
            ('+/-', '+/+'): '+',
            ('+/-', '+/-'): None,
            ('+/-', '-/-'): None,
            ('+/-', '+'): None,
            ('+/-', None): None,
            ('-/-', '+/+'): '+/-',
            ('-/-', '+/-'): None,
            ('-/-', '-/-'): '-/-',
            ('-/-', '+'): None,
            ('-/-', None): '-/-',
            ('+', '+/+'): '+',
            ('+', '+/-'): None,
            ('+', '-/-'): None,
            ('+', '+'): None,
            ('+', None): None,
            (None, '+/+'): '+/-',
            (None, '+/-'): None,
            (None, '-/-'): '-/-',
            (None, '+'): None,
            (None, None): '-/-',
        }.get((zm, zf), None)

    def genotype_from_litter(self, subject, force=False):
        if not subject.litter:
            return
        bp = subject.litter.breeding_pair
        if not bp:
            return
        logger.debug("Genotype from litter for subject %s", subject.nickname)
        mother = bp.mother1
        father = bp.father
        alleles_m = self._existing_alleles(mother)
        alleles_f = self._existing_alleles(father)
        alleles = set(alleles_m).union(set(alleles_f))
        for allele in alleles:
            zm, zf = self._get_parents_alleles(subject, allele)
            z = self._zygosity_from_parents(zm, zf)
            if not z:
                continue
            logger.debug("Zygosity %s: %s %s from parents %s (%s) and %s (%s).",
                         subject, allele, z,
                         mother, zm,
                         father, zf,
                         )
            # If there is a conflict when setting a litter, we don't update the zygosities.
            self._create_zygosity(subject, allele, z, force=force)


@receiver(post_delete)
def delete_zygosity_rule(sender, instance, **kwargs):
    if isinstance(instance, ZygosityRule):
        _update_zygosyties(instance.line, instance.sequence0)


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

    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    allele = models.ForeignKey('Allele', on_delete=models.CASCADE)
    zygosity = models.IntegerField(choices=ZYGOSITY_TYPES)

    @staticmethod
    def from_symbol(symbol):
        return ZYGOSITY_SYMBOLS.index(symbol)

    def symbol(self):
        return (ZYGOSITY_SYMBOLS[self.zygosity]
                if self.zygosity is not None else '?')

    def __str__(self):
        return "{0:s} {1:s}".format(
            str(self.allele), self.symbol())

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
