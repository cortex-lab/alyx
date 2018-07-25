from django import forms
from django.db import models
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.postgres.fields import JSONField

from .models import Note, Lab, LabMembership, LabLocation
from alyx.base import BaseAdmin


class LabAdmin(BaseAdmin):
    fields = ['name', 'institution', 'address', 'timezone']
    list_display = fields


class LabMembershipAdmin(BaseAdmin):
    fields = ['user', 'lab', 'role', 'start_date', 'end_date']
    list_display = fields


class LabLocationAdmin(BaseAdmin):
    fields = ['name']


class NoteAdmin(BaseAdmin):
    list_display = ['user', 'date_time', 'content_object', 'text']
    list_display_links = ['date_time']
    fields = ['user', 'date_time', 'text', 'content_type', 'object_id']


class NoteInline(GenericTabularInline):
    model = Note
    extra = 1
    fields = ('user', 'date_time', 'text')
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

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Lab, LabAdmin)
admin.site.register(LabMembership, LabMembershipAdmin)
admin.site.register(LabLocation, LabLocationAdmin)
admin.site.register(Note, NoteAdmin)
