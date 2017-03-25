from django.contrib import admin
from .models import (PupilTracking, HeadTracking, EventSeries, IntervalSeries,
                     OptogeneticStimulus, Pharmacology)
from alyx.base import BaseAdmin


class PupilTrackingAdmin(BaseAdmin):
    fields = ['description', 'movie', 'eye', 'x_y_d',
              'generating_software', 'provenance_directory']


admin.site.register(PupilTracking, PupilTrackingAdmin)
admin.site.register(HeadTracking)
admin.site.register(EventSeries)
admin.site.register(IntervalSeries)
admin.site.register(OptogeneticStimulus)
admin.site.register(Pharmacology)
