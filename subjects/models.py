import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField, JSONField
from datetime import datetime, timezone

class Species(models.Model):
    binomial = models.CharField(max_length=255, primary_key=True)
    display_name = models.CharField(max_length=255)

    def __str__(self):
        return self.display_name

    class Meta:
        verbose_name_plural = "species"

class Litter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descriptive_name = models.CharField(max_length=255)
    mother = models.ForeignKey('Subject', null=True, blank=True, related_name="litter_mother")
    father = models.ForeignKey('Subject', null=True, blank=True, related_name="litter_father")
    notes = models.TextField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.descriptive_name

class Strain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descriptive_name = models.CharField(max_length=255) # http://www.informatics.jax.org/mgihome/nomen/

    def __str__(self):
        return self.descriptive_name

class Genotype(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descriptive_name = models.CharField(max_length=255) # http://www.informatics.jax.org/mgihome/nomen/

    def __str__(self):
        return self.descriptive_name

class Source(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.descriptive_name

class Subject(models.Model):
    SEXES = (
    	('M', 'Male'),
    	('F', 'Female'),
    	('U', 'Unknown')
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nickname = models.CharField(max_length=255, null=True, blank=True, unique=True)
    species = models.ForeignKey(Species)
    litter = models.ForeignKey('Litter', null=True, blank=True)
    sex = models.CharField(max_length=1, choices=SEXES, default='U')
    strain = models.ForeignKey(Strain, null=True, blank=True)
    genotype = models.ForeignKey(Genotype, null=True, blank=True)
    source = models.ForeignKey(Source, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, related_name='subjects_responsible', null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    def alive(self):
        return self.death_date is None
    alive.boolean = True

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
