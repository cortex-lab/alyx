from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

import uuid
from actions.models import EphysSession
from alyx.base import BaseModel


class ProbeInsertion(models.Model):
    """
    Describes a probe insertion trajectory - always a straight line
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    INSERTION_DATA_SOURCES = [
        (70, 'Ephys aligned histology track',),
        (50, 'Histology track',),
        (30, 'Micro-manipulator',),
        (10, 'Planned',),
    ]

    session = models.ForeignKey(EphysSession, blank=True, null=True, on_delete=models.CASCADE)
    x = models.FloatField(null=True, help_text="medio-lateral coordinate (mm), right +,"
                                               " relative to Bregma",
                          verbose_name='x-ml (mm)')
    y = models.FloatField(null=True,
                          help_text="antero-posterior coordinate (mm), front +, relative "
                                    "to Bregma",
                          verbose_name='y-ap (mm)')
    z = models.FloatField(null=True,
                          help_text="dorso-ventral coordinate (mm), up +, relative to Bregma",
                          verbose_name='z-dv (mm)')
    depth = models.FloatField(null=True,
                              help_text="probe insertion depth (mm)")
    theta = models.FloatField(null=True,
                              help_text="Polar angle ie. from vertical, (degrees) [0-180]",
                              validators=[MinValueValidator(0), MaxValueValidator(180)])
    phi = models.FloatField(null=True,
                            help_text="Azimuth from right (degrees), anti-clockwise, [0-360]",
                            validators=[MinValueValidator(0), MaxValueValidator(360)])
    roll = models.FloatField(null=True,
                             validators=[MinValueValidator(0), MaxValueValidator(360)])
    provenance = models.IntegerField(default=10, choices=INSERTION_DATA_SOURCES)
    probe_label = models.CharField(blank=True, null=True, max_length=255)


class BrainLocation(BaseModel):
    """
    Allen Brain Atlas labels
    """
    pass
