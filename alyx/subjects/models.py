import csv
from datetime import datetime
import logging
import os.path as op
import urllib

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from alyx.base import BaseModel
from equipment.models import LabLocation
from actions.models import ProcedureType, OtherAction, Weighing, WaterAdministration

logger = logging.getLogger(__name__)


class Subject(BaseModel):
    """Metadata about an experimental subject (animal or human)."""
    SEXES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('U', 'Unknown')
    )

    nickname = models.SlugField(max_length=255,
                                unique=True,
                                allow_unicode=True,
                                default='-',
                                help_text="Easy-to-remember, unique name "
                                          "(e.g. 'Hercules').")
    species = models.ForeignKey('Species', null=True, blank=True,
                                on_delete=models.SET_NULL,
                                )
    litter = models.ForeignKey('Litter', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               )
    sex = models.CharField(max_length=1, choices=SEXES,
                           null=True, blank=True, default='U')
    strain = models.ForeignKey('Strain', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               )
    genotype = models.ManyToManyField('Allele', through='Zygosity')
    genotype_test = models.ManyToManyField('Sequence', through='GenotypeTest')
    source = models.ForeignKey('Source', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               )
    line = models.ForeignKey('Line', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name='subjects_responsible',
                                         help_text="Who has primary or legal responsibility "
                                         "for the subject.")
    cage = models.ForeignKey('Cage', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    implant_weight = models.FloatField(help_text="Implant weight in grams",
                                       null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    ear_mark = models.CharField(max_length=32, null=True, blank=True)

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

    def water_restriction_date(self):
        actname = 'Put on water restriction'
        proc = ProcedureType.objects.filter(name=actname)
        if not proc:
            return
        proc = proc[0]
        restriction = OtherAction.objects.filter(subject__id=self.id,
                                                 procedures__id=proc.id)
        restriction = restriction.order_by('-date_time')
        if not restriction:
            return
        return restriction[0].date_time

    def reference_weighing(self):
        wr_date = self.water_restriction_date()
        weighings = Weighing.objects.filter(subject__id=self.id,
                                            date_time__lte=wr_date)
        weighings = weighings.order_by('-date_time')
        if not weighings:
            return
        return weighings[0]

    def current_weighing(self):
        weighings = Weighing.objects.filter(subject__id=self.id)
        weighings = weighings.order_by('-date_time')
        if not weighings:
            return
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

    def __str__(self):
        return self.nickname


class Species(BaseModel):
    """A single species, identified uniquely by its binomial name."""
    binomial = models.CharField(max_length=255,
                                help_text="Binomial name, "
                                "e.g. \"mus musculus\"")
    display_name = models.CharField(max_length=255,
                                    help_text="common name, e.g. \"mouse\"")

    def __str__(self):
        return self.display_name

    class Meta:
        verbose_name_plural = "species"


class Litter(BaseModel):
    """A litter, containing a mother, father, and children with a
    shared date of birth."""
    descriptive_name = models.CharField(max_length=255)
    mother = models.ForeignKey('Subject', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               related_name="litter_mother")
    father = models.ForeignKey('Subject', null=True, blank=True,
                               on_delete=models.SET_NULL,
                               related_name="litter_father")
    line = models.ForeignKey('Line', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    cage = models.ForeignKey('Cage', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    notes = models.TextField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.descriptive_name


class Cage(BaseModel):
    CAGE_TYPES = (
        ('I', 'IVC'),
        ('R', 'Regular'),
    )

    cage_label = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=1, choices=CAGE_TYPES, default='I',
                            help_text="Is this an IVC or regular cage?")
    line = models.ForeignKey('Line', null=True, blank=True,
                             on_delete=models.SET_NULL,
                             )
    location = models.ForeignKey(LabLocation)

    def __str__(self):
        return self.cage_label


class Line(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    gene_name = models.CharField(max_length=1023)
    auto_name = models.SlugField(max_length=255)

    def __str__(self):
        return self.name


class Strain(BaseModel):
    """A strain with a standardised name. """
    descriptive_name = models.CharField(max_length=255,
                                        help_text="Standard descriptive name E.g. \"C57BL/6J\", "
                                        "http://www.informatics.jax.org/mgihome/nomen/")
    description = models.TextField(null=True, blank=True)

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

    def __str__(self):
        return self.informal_name


class Zygosity(BaseModel):
    """
    A junction table between Subject and Allele.
    """
    CAGE_TYPES = (
        (0, 'Absent'),
        (1, 'Heterozygous'),
        (2, 'Homozygous'),
        (3, 'Present'),
    )
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    allele = models.ForeignKey('Allele', on_delete=models.CASCADE)
    zygosity = models.IntegerField(choices=CAGE_TYPES)

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


class Source(BaseModel):
    """A supplier / source of subjects."""
    name = models.CharField(max_length=255)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name
