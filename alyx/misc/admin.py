from pytz import all_timezones

from django import forms
from django.db import models
from django.contrib import admin
from django.contrib.admin.widgets import AdminFileWidget
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.postgres.fields import JSONField

from .models import Note, Lab, LabMembership, LabLocation
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
    fields = ['name', 'institution', 'address', 'timezone',
              'reference_weight_pct', 'zscore_weight_pct']
    list_display = fields


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


admin.site.register(Lab, LabAdmin)
admin.site.register(LabMembership, LabMembershipAdmin)
admin.site.register(LabLocation, LabLocationAdmin)
admin.site.register(Note, NoteAdmin)
