from django.db import models
from data.models import Fileset

class PupilTracking(models.Model):
    """Describes the results of a pupil tracking algorithm."""

    EYES = (
        ('L', 'Left'),
        ('R', 'Right'),
    )
    x_y_d = models.ForeignKey(Fileset, blank=True, null=True, related_name="pupil_tracking_x_y_d",
                              help_text="3xn timeseries giving x and y coordinates of center plus diameter")
    movie = models.ForeignKey(Fileset, blank=True, null=True, related_name="pupil_tracking_movie",
                                 help_text="Link to raw data")
    eye = models.CharField(max_length=1,
                           choices=EYES,
                           default='L', blank=True, null=True,
                           help_text="Which eye was tracked; left or right")
    description = models.TextField(blank=True, null=True,
                                   help_text="misc. narrative e.g. (“unit: mm” or “unknown scale factor”)")
    generating_software = models.CharField(max_length=255, null=True, blank=True,
                                           help_text="e.g. “PupilTracka 0.8.3”")
    provenance_directory = models.ForeignKey(Fileset, blank=True, null=True, related_name="pupil_tracking_provenance",
                                             help_text="link to directory containing intermediate results")

class HeadTracking(models.Model):
    pass

class EventSeries(models.Model):
    pass

class IntervalSeries(models.Model):
    pass

class OptogeneticStimulus(models.Model):
    pass

class Pharmacology(models.Model):
    pass