from django.contrib import admin
from .models import BrainLocation, CoordinateTransformation
from alyx.base import BaseAdmin


class BrainLocationAdmin(BaseAdmin):
    fields = ['name', 'allen_location_ontology', 'description', 'stereotaxic_coordinates']


class CoordinateTransformationAdmin(BaseAdmin):
    fields = ['name', 'allen_location_ontology', 'description', 'origin', 'transformation_matrix']


admin.site.register(BrainLocation, BrainLocationAdmin)
admin.site.register(CoordinateTransformation, CoordinateTransformationAdmin)
