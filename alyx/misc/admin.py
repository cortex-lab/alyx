from pytz import all_timezones
import uuid

from django import forms
from django.db import models
from django.contrib import admin
from django.contrib.admin.widgets import AdminFileWidget
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.postgres.fields import JSONField

from subjects.models import Subject
from misc.models import Note, Lab, LabMembership, LabLocation, CageType, Enrichment, Food, Housing
from alyx.base import BaseAdmin


class LabForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(LabForm, self).__init__(*args, **kwargs)
        self.fields['reference_weight_pct'].help_text =\
            'Threshold ratio triggers a warning using the Reference Weight method (0-1)'
        self.fields['reference_weight_pct'].label = 'Reference Weight Ratio'
        self.fields['zscore_weight_pct'].help_text =\
            'Threshold ratio triggers a warning is raised using the Z-Score method (0-1)'
        self.fields['zscore_weight_pct'].label = 'Z-score Weight Ratio'

    def clean_reference_weight_pct(self):
        ref = self.cleaned_data['reference_weight_pct']
        ref = max(ref, 0)
        if ref > 1:
            ref = ref / 100
        return ref

    def clean_zscore_weight_pct(self):
        ref = self.cleaned_data['zscore_weight_pct']
        ref = max(ref, 0)
        if ref > 1:
            ref = ref / 100
        return ref

    def clean_timezone(self):
        ref = self.cleaned_data['timezone']
        if ref not in all_timezones:
            raise forms.ValidationError(
                ("Time Zone is incorrect here is the list (column TZ Database Name):  "
                 "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"))
        return ref


class LabAdmin(BaseAdmin):
    form = LabForm
    list_display = ['name', 'institution', 'address', 'timezone',
                    'reference_weight_pct', 'zscore_weight_pct']
    list_select_related = ['cage_type', 'enrichment', 'food']
    fields = list_display + list_select_related + ['cage_cleaning_frequency_days', 'light_cycle']


class LabMembershipAdmin(BaseAdmin):
    fields = ['user', 'lab', 'role', 'start_date', 'end_date']
    list_display = fields


class LabLocationAdmin(BaseAdmin):
    fields = ['name', 'lab']
    list_display = fields


class AdminImageWidget(AdminFileWidget):
    def render(self, name, value, attrs=None, renderer=None):
        output = []
        if value and getattr(value, "url", None):
            image_url = value.url
            file_name = str(value)
            output.append(('<a href="%s" target="_blank">'
                           '<img src="%s" width="400" alt="%s" /></a><br>') %
                          (image_url, image_url, file_name))
        output.append(super(AdminFileWidget, self).render(name, value, attrs, renderer))
        return ''.join(output)


class ImageWidgetAdmin(BaseAdmin):
    image_fields = []

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in self.image_fields:
            request = kwargs.pop("request", None)  # noqa
            kwargs['widget'] = AdminImageWidget
            return db_field.formfield(**kwargs)
        return super(ImageWidgetAdmin, self).formfield_for_dbfield(db_field, **kwargs)


class NoteAdmin(ImageWidgetAdmin):
    list_display = ['user', 'date_time', 'content_object', 'text', 'image']
    list_display_links = ['date_time']
    image_fields = ['image']
    fields = ['user', 'date_time', 'text', 'image', 'content_type', 'object_id']


class NoteInline(GenericTabularInline):
    model = Note
    extra = 1
    fields = ('user', 'date_time', 'text', 'image')
    image_fields = ('image',)
    classes = ['collapse']

    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(
                           attrs={'rows': 3,
                                  'cols': 30})},
        JSONField: {'widget': forms.Textarea(
                    attrs={'rows': 3,
                           'cols': 30})},
        models.CharField: {'widget': forms.TextInput(attrs={'size': 16})},
    }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Logged-in user by default.
        if db_field.name == 'user':
            kwargs['initial'] = request.user
        return super(NoteInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in self.image_fields:
            request = kwargs.pop("request", None)  # noqa
            kwargs['widget'] = AdminImageWidget
            return db_field.formfield(**kwargs)
        return super(NoteInline, self).formfield_for_dbfield(db_field, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False


class CageTypeAdmin(BaseAdmin):
    fields = ('name', 'description',)
    list_display = fields
    search_fields = ('name',)


class EnrichmentAdmin(BaseAdmin):
    fields = ('name', 'description',)
    list_display = fields
    search_fields = ('name',)


class FoodAdmin(BaseAdmin):
    fields = ('name', 'description',)
    list_display = fields
    search_fields = ('name',)


class HousingAdminForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.Meta.formfield_callback.keywords['request']
        self.user = request.user
        subs = Subject.objects.filter(death_date__isnull=True)
        lab = self.user.lab_id()
        if lab:
            subs = Subject.objects.filter(lab__in=lab)
            self.fields['cage_type'].initial = lab[0].cage_type
            self.fields['enrichment'].initial = lab[0].enrichment
            self.fields['light_cycle'].initial = lab[0].light_cycle
            self.fields['food'].initial = lab[0].food
            self.fields['cage_cleaning_frequency_days'].initial =\
                lab[0].cage_cleaning_frequency_days
        self.fields['subjects'].queryset = subs.order_by('lab', 'nickname')


class HousingAdmin(BaseAdmin):

    form = HousingAdminForm

    fields = ['subjects',
              ('start_datetime', 'end_datetime',),
              ('cage_type', 'cage_name'),
              ('enrichment', 'light_cycle',),
              ('food', 'cage_cleaning_frequency_days')]
    filter_horizontal = ('subjects',)
    list_display = ('lab', 'cage_name', 'subjects_l', 'start_datetime', 'end_datetime',)

    def save_model(self, request, obj, form, change):
        subs = obj.subjects.all()
        # if the modified object has already a end date, it's in the past and don't bother
        super().save_model(request, obj, form, change)
        if obj.end_datetime:
            return
        # many to many fields are updated after save
        subs = form.data.get('subjects')
        if isinstance(subs, str):
            subs = [subs]
        subs = [uuid.UUID(s) for s in subs]
        housings = Housing.objects.filter(end_datetime__isnull=True).exclude(pk=obj.pk)
        housings = housings.filter(subjects__pk__in=subs).distinct()
        obj.update_and_create(housings, moved_subjects_pk=subs)

    def subjects_l(self, obj):
        return ', '.join(map(str, obj.subjects.all()))
    subjects_l.short_description = 'subjects'


admin.site.register(Housing, HousingAdmin)
admin.site.register(Lab, LabAdmin)
admin.site.register(LabMembership, LabMembershipAdmin)
admin.site.register(LabLocation, LabLocationAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(CageType, CageTypeAdmin)
admin.site.register(Enrichment, EnrichmentAdmin)
admin.site.register(Food, FoodAdmin)
