import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField, JSONField
from equipment.models import LabLocation
from datetime import datetime, timezone
import urllib

class Subject(models.Model):
    """Metadata about an experimental subject (animal or human)."""
    SEXES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('U', 'Unknown')
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nickname = models.SlugField(max_length=255, unique=True, allow_unicode=True,
                                help_text="Easy-to-remember, unique name (e.g. “Hercules”).")
    species = models.ForeignKey('Species', null=True, blank=True)
    litter = models.ForeignKey('Litter', null=True, blank=True)
    sex = models.CharField(max_length=1, choices=SEXES, null=True, blank=True, default='U')
    strain = models.ForeignKey('Strain', null=True, blank=True)
    genotype = models.ManyToManyField('Allele', through='Zygosity')
    source = models.ForeignKey('Source', null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, related_name='subjects_responsible', null=True, blank=True,
                                         help_text="Who has primary or legal responsibility for the subject.")
    cage = models.ForeignKey('Cage', null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    ear_mark = models.CharField(max_length=32, null=True, blank=True)

    def alive(self):
        return self.death_date is None
    alive.boolean = True

    def nicknamesafe(self):
        return urllib.parse.quote(str(nickname), '')

    def age_days(self):
        if (self.death_date is None & self.birth_date is not None):
            age = datetime.now(timezone.utc) - self.birth_date # subject still alive
        elif (self.death_date is not None & self.birth_date is not None):
            age = self.death_date - self.birth_date # subject is dead
        else: # not dead or born!
            return None
        return age.days

    def __str__(self):
        return self.nickname

class Species(models.Model):
    """A single species, identified uniquely by its binomial name."""
    binomial = models.CharField(max_length=255, primary_key=True,
                                help_text="Binomial name, e.g. \"mus musculus\"")
    display_name = models.CharField(max_length=255, help_text="common name, e.g. \"mouse\"")

    def __str__(self):
        return self.display_name

    class Meta:
        verbose_name_plural = "species"

class Litter(models.Model):
    """A litter, containing a mother, father, and children with a shared date of birth."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descriptive_name = models.CharField(max_length=255)
    mother = models.ForeignKey('Subject', null=True, blank=True, related_name="litter_mother")
    father = models.ForeignKey('Subject', null=True, blank=True, related_name="litter_father")
    notes = models.TextField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.descriptive_name


class Cage(models.Model):
    CAGE_TYPES = (
        ('I', 'IVC'),
        ('R', 'Regular'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cage_label = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=1, choices=CAGE_TYPES, default='I', help_text=
                            "Is this an IVC or regular cage?")
    location = models.ForeignKey(LabLocation)

    def __str__(self):
        return self.cage_label


class Strain(models.Model):
    """A strain with a standardised name. """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descriptive_name = models.CharField(max_length=255,
        help_text="Standard descriptive name E.g. \"C57BL/6J\", http://www.informatics.jax.org/mgihome/nomen/")
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.descriptive_name

class Allele(models.Model):
    """A single allele."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    standard_name = models.CharField(max_length=1023, # these could be really long, 255 characters might not be enough!
        help_text="MGNC-standard genotype name e.g. Pvalb<tm1(cre)Arbr>, http://www.informatics.jax.org/mgihome/nomen/")
    informal_name = models.CharField(max_length=255, help_text="informal name in lab, e.g. Pvalb-Cre")

    def __str__(self):
        return self.informal_name

class Zygosity(models.Model):
    """
    A junction table between Subject and Allele.
    """
    CAGE_TYPES = (
        (0, 'Absent'),
        (1, 'Heterozygous'),
        (2, 'Homozygous'),
    )
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    allele = models.ForeignKey('Allele', on_delete=models.CASCADE)
    zygosity = models.IntegerField(choices=CAGE_TYPES)

    class Meta:
        verbose_name_plural = "zygosities"

class Source(models.Model):
    """A supplier / source of subjects."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

