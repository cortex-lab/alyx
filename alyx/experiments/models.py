from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

import uuid
from actions.models import EphysSession
from alyx.base import BaseModel


class ProbeModel(BaseModel):
    """
    Metadata describing each probe model
    """
    probe_manufacturer = models.CharField(max_length=255)
    probe_model = models.CharField(unique=True, max_length=255,
                                   help_text="manufacturer's part number e.g. A4x8-5mm-100-20")
    description = models.CharField(max_length=255, null=True, blank=True,
                                   help_text="optional informal description e.g. "
                                   "'Michigan 4x4 tetrode'; 'Neuropixels phase 2 option 1'")


class ProbeInsertion(BaseModel):
    """
    Describe an electrophysiology probe insertion used for recording
    """
    session = models.ForeignKey(EphysSession, blank=True, null=True, on_delete=models.CASCADE)
    model = models.ForeignKey(ProbeModel, blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return "%s %s" % (self.name, str(self.session))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'session'],
                                    name='unique_probe_insertion_name_per_session')
        ]


class TrajectoryEstimate(models.Model):
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

    probe_insertion = models.ForeignKey(ProbeInsertion, blank=True, null=True,
                                        on_delete=models.CASCADE,
                                        related_name='trajectory_estimate')
    x = models.FloatField(null=True, help_text="brain surface medio-lateral coordinate (um) of"
                                               "the insertion, right +, relative to Bregma",
                          verbose_name='x-ml (um)')
    y = models.FloatField(null=True,
                          help_text="brain surface antero-posterior coordinate (um) of the "
                                    "insertion, front +, relative to Bregma",
                          verbose_name='y-ap (um)')
    z = models.FloatField(null=True,
                          help_text="brain surface dorso-ventral coordinate (um) of the insertion"
                                    ", up +, relative to Bregma",
                          verbose_name='z-dv (um)')
    depth = models.FloatField(null=True,
                              help_text="probe insertion depth (um)")
    theta = models.FloatField(null=True,
                              help_text="Polar angle ie. from vertical, (degrees) [0-180]",
                              validators=[MinValueValidator(0), MaxValueValidator(180)])
    phi = models.FloatField(null=True,
                            help_text="Azimuth from right (degrees), anti-clockwise, [0-360]",
                            validators=[MinValueValidator(0), MaxValueValidator(360)])
    roll = models.FloatField(null=True,
                             validators=[MinValueValidator(0), MaxValueValidator(360)])
    provenance = models.IntegerField(default=10, choices=INSERTION_DATA_SOURCES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provenance', 'probe_insertion'],
                                    name='unique_trajectory_per_provenance')
        ]

# class BrainLocation(BaseModel):
#     """
#     Allen Brain Atlas labels
#     """
#     pass
