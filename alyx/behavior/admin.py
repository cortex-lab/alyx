from django.contrib import admin
from .models import *
from alyx.base import BaseAdmin


class PupilTrackingAdmin(BaseAdmin):
    fields = ['description', 'movie', 'eye', 'x_y_d',
              'generating_software', 'provenance_directory']


admin.site.register(PupilTracking, PupilTrackingAdmin)
