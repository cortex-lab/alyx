from django.contrib import admin
from alyx.base import BaseAdmin
from .models import *


class BaseActionAdmin(BaseAdmin):
    fields = ['subject', 'date_time', 'users', 'location', 'procedures', 'narrative']


class ProcedureTypeAdmin(BaseAdmin):
    fields = ['name', 'description']


class WaterAdministrationAdmin(BaseAdmin):
    fields = ['subject', 'date_time', 'water_administered', 'hydrogel', 'user']


class WeighingAdmin(BaseAdmin):
    list_display = ['subject', 'weight', 'date_time']
    fields = ['subject', 'date_time', 'weight', 'user', 'weighing_scale']
    ordering = ('-date_time',)


class SurgeryAdmin(BaseActionAdmin):
    list_display = ['subject', 'location', 'date_time']


class NoteAdmin(BaseActionAdmin):
    list_display = ['subject', 'narrative']


admin.site.register(ProcedureType, ProcedureTypeAdmin)
admin.site.register(Weighing, WeighingAdmin)
admin.site.register(WaterAdministration, WaterAdministrationAdmin)

admin.site.register(Experiment, BaseActionAdmin)
admin.site.register(WaterRestriction, BaseActionAdmin)
admin.site.register(OtherAction, BaseActionAdmin)
admin.site.register(VirusInjection, BaseActionAdmin)

admin.site.register(Surgery, SurgeryAdmin)
