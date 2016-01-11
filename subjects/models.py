import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField, JSONField

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
    nickname = models.CharField(max_length=255)
    species = models.ForeignKey(Species)
    sex = models.CharField(max_length=1,
                           choices=SEXES, default='U')
    strain = models.CharField(max_length=255)
    genotype = models.CharField(max_length=255)
    source = models.CharField(max_length=255)
    birth_date_time = models.DateTimeField(null=True, blank=True)
    death_date_time = models.DateTimeField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, related_name = 'subjects_responsible')
    mother = models.ForeignKey("self", null=True, blank=True, related_name="subject_mother")
    father = models.ForeignKey("self", null=True, blank=True, related_name="subject_father")

    notes = models.TextField(null=True, blank=True)

    def alive(self):
        return self.death_date_time is None
    alive.boolean = True

    def __str__(self):
        return self.nickname

class Action(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    users = models.ManyToManyField(User, null=True, blank=True)
    subject = models.ForeignKey(Subject)
    location = models.CharField(max_length=255)
    narrative = models.TextField(null=True, blank=True)
    start_date_time = models.DateTimeField(null=True, blank=True)
    end_date_time = models.DateTimeField(null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=255), size=30,
                      null=True,
                      blank=True)
    JSON = JSONField(null=True, blank=True)

class Weighing(Action):
    weight = models.FloatField()

class Surgery(Action):
    procedure = models.CharField(max_length=255)
    brain_location = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = "surgeries"