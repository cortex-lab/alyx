from django.contrib import admin
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin
from .models import (Appliance, WeighingScale, Amplifier, PipettePuller, DAQ,
                     VirusBatch, Lab, LabMembership, LabLocation, EquipmentModel
                     )
from alyx.base import BaseAdmin


class ApplianceChildAdmin(PolymorphicChildModelAdmin):
    base_model = Appliance


class WeighingScaleAdmin(ApplianceChildAdmin):
    base_model = WeighingScale


class AmplifierAdmin(ApplianceChildAdmin):
    base_model = Amplifier


class PipettePullerAdmin(ApplianceChildAdmin):
    base_model = PipettePuller


class DAQAdmin(ApplianceChildAdmin):
    base_model = DAQ


class ApplianceParentAdmin(PolymorphicParentModelAdmin):
    base_model = Appliance
    child_models = (
        (WeighingScale, WeighingScaleAdmin),
        (Amplifier, AmplifierAdmin),
        (PipettePuller, PipettePullerAdmin),
        (DAQ, DAQAdmin)
    )
    polymorphic_list = True
    list_display = ('descriptive_name', 'polymorphic_ctype',
                    'location', 'equipment_model')
    pk_regex = '([\w-]+)'


class LabAdmin(BaseAdmin):
    fields = ['name', 'institution', 'address', 'timezone']
    list_display = fields


class LabMembershipAdmin(BaseAdmin):
    fields = ['user', 'lab', 'role', 'start_date', 'end_date']
    list_display = fields


class LabLocationAdmin(BaseAdmin):
    fields = ['name']


class EquipmentManufacturerAdmin(BaseAdmin):
    fields = ['name', 'description']


class EquipmentModelAdmin(BaseAdmin):
    fields = ['model_name', 'manufacturer', 'description']


class VirusBatchAdmin(BaseAdmin):
    fields = ['virus_type', 'virus_source', 'date_time_made', 'nominal_titer', 'description']


admin.site.register(Appliance, ApplianceParentAdmin)

admin.site.register(Lab, LabAdmin)
admin.site.register(LabMembership, LabMembershipAdmin)
admin.site.register(LabLocation, LabLocationAdmin)
admin.site.register(EquipmentModel, EquipmentModelAdmin)
admin.site.register(VirusBatch, VirusBatchAdmin)
