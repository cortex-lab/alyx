from django.contrib import admin
from alyx.base import BaseAdmin
from .models import *
from subjects.models import Subject


class BaseActionAdmin(BaseAdmin):
    fields = ['subject', 'start_time', 'end_time', 'users',
              'location', 'procedures', 'narrative']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'subject':
            kwargs["queryset"] = Subject.objects.filter(responsible_user=request.user,
                                                        death_date=None,
                                                        ).order_by('nickname')
        return super(BaseActionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class ProcedureTypeAdmin(BaseActionAdmin):
    fields = ['name', 'description']


class WaterAdministrationAdmin(BaseActionAdmin):
    fields = ['subject', 'date_time', 'water_administered', 'hydrogel', 'user']


class WeighingAdmin(BaseActionAdmin):
    list_display = ['subject', 'weight', 'date_time']
    fields = ['subject', 'date_time', 'weight', 'user', 'weighing_scale']
    ordering = ('-date_time',)


class SurgeryAdmin(BaseActionAdmin):
    list_display = ['subject', 'location', 'start_time']
    fields = ['subject', 'location', 'outcome_type', 'start_time']


admin.site.register(ProcedureType, ProcedureTypeAdmin)
admin.site.register(Weighing, WeighingAdmin)
admin.site.register(WaterAdministration, WaterAdministrationAdmin)

admin.site.register(Experiment, BaseActionAdmin)
admin.site.register(WaterRestriction, BaseActionAdmin)
admin.site.register(OtherAction, BaseActionAdmin)
admin.site.register(VirusInjection, BaseActionAdmin)

admin.site.register(Surgery, SurgeryAdmin)
