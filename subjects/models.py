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
    sex = models.CharField(max_length=1,
                           choices=SEXES, default='U')
    strain = models.CharField(max_length=255, null=True, blank=True)
    genotype = models.CharField(max_length=255, null=True, blank=True)
    source = models.CharField(max_length=255, null=True, blank=True)
    birth_date_time = models.DateTimeField(null=True, blank=True)
    death_date_time = models.DateTimeField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, related_name = 'subjects_responsible', null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    def alive(self):
        return self.death_date_time is None
    alive.boolean = True

    def age_days(self):
        if self.alive():
            age = datetime.now(timezone.utc) - self.birth_date_time
        else:
            age = self.death_date_time - self.birth_date_time
        return age.days

    def __str__(self):
        return self.nickname

class Litter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descriptive_name = models.CharField(max_length=255)
    mother = models.ForeignKey("Subject", null=True, blank=True, related_name="litter_mother")
    father = models.ForeignKey("Subject", null=True, blank=True, related_name="litter_father")
