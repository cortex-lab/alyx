from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Q
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from django.utils.html import format_html

from alyx.base import BaseAdmin, DefaultListFilter
from .models import (OtherAction, ProcedureType, Session, Surgery, VirusInjection,
                     WaterAdministration, WaterRestriction, Weighing,
                     )
from subjects.models import Subject
from subjects.admin import get_admin_url


class ActiveFilter(DefaultListFilter):
    title = 'active'
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        return (
            (None, 'Active'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(start_time__isnull=False,
                                   end_time__isnull=True,
                                   )
        elif self.value == 'all':
            return queryset.all()


class BaseActionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(BaseActionForm, self).__init__(*args, **kwargs)
        if 'users' in self.fields:
            self.fields['users'].queryset = User.objects.all().order_by('username')
        if 'user' in self.fields:
            self.fields['user'].queryset = User.objects.all().order_by('username')
        if 'subject' in self.fields:
            inst = self.instance
            q = Q(responsible_user=self.current_user, death_date=None)
            if getattr(inst, 'subject', None):
                q |= Q(pk=inst.subject.pk)
            qs = Subject.objects.filter(q).order_by('nickname')
            self.fields['subject'].queryset = qs


class BaseActionAdmin(BaseAdmin):
    fields = ['subject', 'start_time', 'end_time', 'users',
              'location', 'procedures', 'narrative']

    form = BaseActionForm

    def get_form(self, request, obj=None, **kwargs):
        form = super(BaseActionAdmin, self).get_form(request, obj, **kwargs)
        form.current_user = request.user
        return form


class ProcedureTypeAdmin(BaseActionAdmin):
    fields = ['name', 'description']


class WaterAdministrationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(WaterAdministrationForm, self).__init__(*args, **kwargs)
        # Only show subjects that are on water restriction.
        self.fields['subject'].queryset = Subject.objects.filter(
            pk__in=[wr.subject.pk
                    for wr in WaterRestriction.objects.filter(start_time__isnull=False,
                                                              end_time__isnull=True)],
        )
        self.fields['user'].queryset = User.objects.all().order_by('username')


class WaterAdministrationAdmin(BaseActionAdmin):
    form = WaterAdministrationForm

    fields = ['subject', 'date_time', 'water_administered', 'hydrogel', 'user']
    list_display = ['subject_l', 'water_administered', 'date_time', 'hydrogel']
    list_display_links = ('water_administered',)
    readonly_fields = ['subject_l']
    ordering = ['-date_time', 'subject__nickname']
    search_fields = ['subject__nickname']
    list_filter = [('subject', RelatedDropdownFilter)]

    def subject_l(self, obj):
        url = get_admin_url(obj.subject)
        return format_html('<a href="{url}">{subject}</a>', subject=obj.subject or '-', url=url)
    subject_l.short_description = 'subject'


class WaterRestrictionAdmin(BaseActionAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'subject':
            kwargs["queryset"] = Subject.objects.filter(death_date=None,
                                                        ).order_by('nickname')
        return super(BaseActionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    list_display = ['subject', 'start_time',
                    'reference_weighing', 'current_weighing',
                    'water_requirement_total', 'water_requirement_remaining',
                    'is_active',
                    ]
    list_display_links = ('start_time',)
    readonly_fields = ['reference_weighing', 'current_weighing',
                       'water_requirement_total', 'water_requirement_remaining',
                       'is_active',
                       ]
    ordering = ['-start_time', 'subject__nickname']
    search_fields = ['subject__nickname']
    list_filter = [('subject', RelatedDropdownFilter),
                   ActiveFilter,
                   ]

    def subject_l(self, obj):
        url = get_admin_url(obj.subject)
        return format_html('<a href="{url}">{subject}</a>', subject=obj.subject or '-', url=url)
    subject_l.short_description = 'subject'

    def reference_weighing(self, obj):
        if not obj.subject:
            return
        w = obj.subject.reference_weighing()
        return w.weight if w else None
    reference_weighing.short_description = 'ref weighing'

    def current_weighing(self, obj):
        if not obj.subject:
            return
        w = obj.subject.current_weighing()
        return w.weight if w else None
    current_weighing.short_description = 'current weighing'

    def water_requirement_total(self, obj):
        if not obj.subject:
            return
        return '%.3f' % obj.subject.water_requirement_total()
    water_requirement_total.short_description = 'water req tot'

    def water_requirement_remaining(self, obj):
        if not obj.subject:
            return
        return '%.3f' % obj.subject.water_requirement_remaining()
    water_requirement_remaining.short_description = 'water req rem'

    def is_active(self, obj):
        return obj.is_active()
    is_active.boolean = True


class WeighingAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'weight', 'date_time']
    fields = ['subject', 'date_time', 'weight', 'user', 'weighing_scale']
    ordering = ('-date_time',)
    list_display_links = ('weight',)
    readonly_fields = ['subject_l']

    def subject_l(self, obj):
        url = get_admin_url(obj.subject)
        return format_html('<a href="{url}">{subject}</a>', subject=obj.subject or '-', url=url)
    subject_l.short_description = 'subject'


# Filters
# ------------------------------------------------------------------------------------------------

class ResponsibleUserListFilter(DefaultListFilter):
    title = 'responsible user'
    parameter_name = 'responsible_user'

    def lookups(self, request, model_admin):
        return (
            (None, 'Me'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(subject__responsible_user=request.user)
        elif self.value == 'all':
            return queryset.all()


class SubjectAliveListFilter(DefaultListFilter):
    title = 'alive'
    parameter_name = 'alive'

    def lookups(self, request, model_admin):
        return (
            (None, 'Yes'),
            ('n', 'No'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(subject__death_date=None)
        if self.value() == 'n':
            return queryset.exclude(subject__death_date=None)
        elif self.value == 'all':
            return queryset.all()


class SurgeryAdmin(BaseActionAdmin):
    list_display = ['subject', 'date', 'users_l', 'procedures_l', 'narrative']
    fields = BaseActionAdmin.fields + ['brain_location', 'outcome_type']
    list_display_links = ['date']
    list_filter = [SubjectAliveListFilter,
                   ResponsibleUserListFilter,
                   ('subject__line', RelatedDropdownFilter),
                   ]

    def date(self, obj):
        return obj.start_time.date()
    date.admin_order_field = 'start_time'

    def users_l(self, obj):
        return ', '.join(map(str, obj.users.all()))
    users_l.short_description = 'users'

    def procedures_l(self, obj):
        return ', '.join(map(str, obj.procedures.all()))
    procedures_l.short_description = 'procedures'


admin.site.register(ProcedureType, ProcedureTypeAdmin)
admin.site.register(Weighing, WeighingAdmin)
admin.site.register(WaterAdministration, WaterAdministrationAdmin)
admin.site.register(WaterRestriction, WaterRestrictionAdmin)

admin.site.register(Session, BaseActionAdmin)
admin.site.register(OtherAction, BaseActionAdmin)
admin.site.register(VirusInjection, BaseActionAdmin)

admin.site.register(Surgery, SurgeryAdmin)
