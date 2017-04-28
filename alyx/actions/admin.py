from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Case, When
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from django.utils.html import format_html

from alyx.base import BaseAdmin, DefaultListFilter
from .models import (OtherAction, ProcedureType, Session, Surgery, VirusInjection,
                     WaterAdministration, WaterRestriction, Weighing,
                     )
from subjects.models import Subject
from subjects.admin import get_admin_url


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


def _bring_to_front(ids, id):
    if id in ids:
        ids.remove(id)
    return [id] + ids


# Admin
# ------------------------------------------------------------------------------------------------

class BaseActionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(BaseActionForm, self).__init__(*args, **kwargs)
        if 'users' in self.fields:
            self.fields['users'].queryset = User.objects.all().order_by('username')
        if 'user' in self.fields:
            self.fields['user'].queryset = User.objects.all().order_by('username')
        if 'subject' in self.fields:
            inst = self.instance
            ids = [s.id for s in Subject.objects.filter(responsible_user=self.current_user,
                                                        death_date=None).order_by('nickname')]
            if getattr(inst, 'subject', None):
                ids = _bring_to_front(ids, inst.subject.pk)
            if getattr(self, 'last_subject_id', None):
                ids = _bring_to_front(ids, self.last_subject_id)
            # These ids first in the list of subjects.
            preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
            self.fields['subject'].queryset = Subject.objects.all().order_by(preserved,
                                                                             'nickname')


class BaseActionAdmin(BaseAdmin):
    fields = ['subject', 'start_time', 'end_time', 'users',
              'location', 'procedures', 'narrative']
    readonly_fields = ['subject_l']

    form = BaseActionForm

    def subject_l(self, obj):
        url = get_admin_url(obj.subject)
        return format_html('<a href="{url}">{subject}</a>', subject=obj.subject or '-', url=url)
    subject_l.short_description = 'subject'

    def _get_last_subject(self, request):
        return getattr(request, 'session', {}).get('last_subject_id', None)

    def get_form(self, request, obj=None, **kwargs):
        form = super(BaseActionAdmin, self).get_form(request, obj, **kwargs)
        form.current_user = request.user
        form.last_subject_id = self._get_last_subject(request)
        return form

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Logged-in user by default.
        if db_field.name == 'user':
            kwargs['initial'] = request.user
        if db_field.name == 'subject':
            subject_id = self._get_last_subject(request)
            if subject_id:
                subject = Subject.objects.get(id=subject_id)
                kwargs['initial'] = subject
        return super(BaseActionAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # Logged-in user by default.
        if db_field.name == 'users':
            kwargs['initial'] = [request.user]
        return super(BaseActionAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs
        )

    def save_model(self, request, obj, form, change):
        subject = getattr(obj, 'subject', None)
        if subject:
            getattr(request, 'session', {})['last_subject_id'] = subject.id.hex
        super(BaseActionAdmin, self).save_model(request, obj, form, change)


class ProcedureTypeAdmin(BaseActionAdmin):
    fields = ['name', 'description']


class WaterAdministrationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(WaterAdministrationForm, self).__init__(*args, **kwargs)
        # Only show subjects that are on water restriction.
        ids = [wr.subject.pk
               for wr in WaterRestriction.objects.filter(start_time__isnull=False,
                                                         end_time__isnull=True)]
        if getattr(self, 'last_subject_id', None):
            ids += [self.last_subject_id]
        # These ids first in the list of subjects.
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
        self.fields['subject'].queryset = Subject.objects.order_by(preserved, 'nickname')
        self.fields['user'].queryset = User.objects.all().order_by('username')
        self.fields['water_administered'].widget.attrs.update({'autofocus': 'autofocus'})


class WaterAdministrationAdmin(BaseActionAdmin):
    form = WaterAdministrationForm

    fields = ['subject', 'date_time', 'water_administered', 'hydrogel', 'user']
    list_display = ['subject_l', 'water_administered', 'date_time', 'hydrogel']
    list_display_links = ('water_administered',)
    ordering = ['-date_time', 'subject__nickname']
    search_fields = ['subject__nickname']
    list_filter = [ResponsibleUserListFilter,
                   ('subject', RelatedDropdownFilter)]


class WaterRestrictionAdmin(BaseActionAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'subject':
            kwargs['queryset'] = Subject.objects.filter(death_date=None,
                                                        ).order_by('nickname')
            subject_id = self._get_last_subject(request)
            if subject_id:
                subject = Subject.objects.get(id=subject_id)
                kwargs['initial'] = subject
        return super(BaseActionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    list_display = ['subject_l', 'start_time',
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
    list_filter = [ResponsibleUserListFilter,
                   ('subject', RelatedDropdownFilter),
                   ActiveFilter,
                   ]

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


class WeighingForm(BaseActionForm):
    def __init__(self, *args, **kwargs):
        super(WeighingForm, self).__init__(*args, **kwargs)
        self.fields['weight'].widget.attrs.update({'autofocus': 'autofocus'})


class WeighingAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'weight', 'date_time']
    fields = ['subject', 'date_time', 'weight', 'user', 'weighing_scale']
    ordering = ('-date_time',)
    list_display_links = ('weight',)
    search_fields = ['subject__nickname']
    list_filter = [ResponsibleUserListFilter,
                   ('subject', RelatedDropdownFilter)]

    form = WeighingForm


class SurgeryAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'date', 'users_l', 'procedures_l', 'narrative']
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
