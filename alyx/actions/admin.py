from django import forms
from django.contrib import admin
from django.db.models import Case, When
from django.urls import reverse
from django.utils.html import format_html
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from rangefilter.filter import DateRangeFilter

from alyx.base import BaseAdmin, DefaultListFilter, BaseInlineAdmin, get_admin_url
from .models import (OtherAction, ProcedureType, Session, Surgery, VirusInjection,
                     WaterAdministration, WaterRestriction, Weighing,
                     )
from data.models import Dataset
from misc.admin import NoteInline
from misc.models import OrderedUser
from subjects.models import Subject
from . import water


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


class CreatedByListFilter(DefaultListFilter):
    title = 'users'
    parameter_name = 'users'

    def lookups(self, request, model_admin):
        return (
            (None, 'Me'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(users=request.user)
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
            self.fields['users'].queryset = OrderedUser.objects.all().order_by('username')
        if 'user' in self.fields:
            self.fields['user'].queryset = OrderedUser.objects.all().order_by('username')
        if 'subject' in self.fields:
            inst = self.instance
            ids = [s.id for s in Subject.objects.filter(responsible_user=self.current_user,
                                                        death_date=None).order_by('nickname')]
            if getattr(inst, 'subject', None):
                ids = _bring_to_front(ids, inst.subject.pk)
            if getattr(self, 'last_subject_id', None):
                ids = _bring_to_front(ids, self.last_subject_id)
            # These ids first in the list of subjects.
            if ids:
                preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
                self.fields['subject'].queryset = Subject.objects.all().order_by(preserved,
                                                                                 'nickname')
            else:
                self.fields['subject'].queryset = Subject.objects.all().order_by('nickname')


class BaseActionAdmin(BaseAdmin):
    fields = ['subject', 'start_time', 'end_time', 'users',
              'location', 'lab', 'procedures', 'narrative']
    readonly_fields = ['subject_l']

    form = BaseActionForm

    def subject_l(self, obj):
        url = get_admin_url(obj.subject)
        return format_html('<a href="{url}">{subject}</a>', subject=obj.subject or '-', url=url)
    subject_l.short_description = 'subject'
    subject_l.admin_order_field = 'subject__nickname'

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
    ordering = ['name']


class WaterAdministrationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(WaterAdministrationForm, self).__init__(*args, **kwargs)
        # Only show subjects that are on water restriction.
        ids = [wr.subject.pk
               for wr in WaterRestriction.objects.filter(start_time__isnull=False,
                                                         end_time__isnull=True).
               order_by('subject__nickname')]
        if getattr(self, 'last_subject_id', None):
            ids += [self.last_subject_id]
        # These ids first in the list of subjects.
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
        self.fields['subject'].queryset = Subject.objects.order_by(preserved, 'nickname')
        self.fields['user'].queryset = OrderedUser.objects.all().order_by('username')
        self.fields['water_administered'].widget.attrs.update({'autofocus': 'autofocus'})


class WaterAdministrationAdmin(BaseActionAdmin):
    form = WaterAdministrationForm

    fields = ['subject', 'date_time', 'water_administered', 'hydrogel', 'user']
    list_display = ['subject_l', 'water_administered', 'date_time', 'hydrogel']
    list_display_links = ('water_administered',)
    list_select_related = ('subject', 'user')
    ordering = ['-date_time', 'subject__nickname']
    search_fields = ['subject__nickname']
    list_filter = [ResponsibleUserListFilter,
                   ('subject', RelatedDropdownFilter)]


class WaterRestrictionForm(forms.ModelForm):
    implant_weight = forms.FloatField()

    def save(self, commit=True):
        implant_weight = self.cleaned_data.get('implant_weight', None)
        subject = self.cleaned_data.get('subject', None)
        if implant_weight:
            subject.implant_weight = implant_weight
            subject.save()
        return super(WaterRestrictionForm, self).save(commit=commit)

    class Meta:
        model = WaterRestriction
        fields = '__all__'


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

    def get_form(self, request, obj=None, **kwargs):
        form = super(WaterRestrictionAdmin, self).get_form(request, obj, **kwargs)
        iw = getattr(getattr(obj, 'subject', None), 'implant_weight', None)
        form.base_fields['implant_weight'].initial = iw
        return form

    form = WaterRestrictionForm

    fields = ['subject', 'implant_weight', 'start_time', 'end_time', 'users', 'narrative']
    list_display = ['subject_w', 'start_time_l',
                    'reference_weighing', 'current_weighing',
                    'water_requirement_total',
                    'water_requirement_today',
                    'water_requirement_remaining',
                    'is_active',
                    ]
    list_select_related = ('subject',)
    list_display_links = ('start_time_l',)
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

    def subject_w(self, obj):
        url = reverse('water-history', kwargs={'subject_id': obj.subject.id})
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.subject.nickname)
    subject_w.short_description = 'subject'

    def start_time_l(self, obj):
        return obj.start_time.date()
    start_time_l.short_description = 'start time'

    def reference_weighing(self, obj):
        if not obj.subject:
            return
        w = water.reference_weighing(obj.subject)
        return w.weight if w else None
    reference_weighing.short_description = 'ref weigh'

    def current_weighing(self, obj):
        if not obj.subject:
            return
        w = water.current_weighing(obj.subject)
        return w.weight if w else None
    current_weighing.short_description = 'cur weigh'

    def water_requirement_total(self, obj):
        if not obj.subject:
            return
        return '%.2f' % water.water_requirement_total(obj.subject)
    water_requirement_total.short_description = 'wat req tot'

    def water_requirement_today(self, obj):
        if not obj.subject:
            return
        return '%.2f' % (water.water_requirement_total(obj.subject) -
                         water.water_requirement_remaining(obj.subject))
    water_requirement_today.short_description = 'wat req tod'

    def water_requirement_remaining(self, obj):
        if not obj.subject:
            return
        return '%.2f' % water.water_requirement_remaining(obj.subject)
    water_requirement_remaining.short_description = 'wat req rem'

    def is_active(self, obj):
        return obj.is_active()
    is_active.boolean = True


class WeighingForm(BaseActionForm):
    def __init__(self, *args, **kwargs):
        super(WeighingForm, self).__init__(*args, **kwargs)
        self.fields['weight'].widget.attrs.update({'autofocus': 'autofocus'})


class WeighingAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'weight', 'date_time']
    list_select_related = ('subject',)
    fields = ['subject', 'date_time', 'weight', 'user', 'weighing_scale']
    ordering = ('-date_time',)
    list_display_links = ('weight',)
    search_fields = ['subject__nickname']
    list_filter = [ResponsibleUserListFilter,
                   ('subject', RelatedDropdownFilter)]

    form = WeighingForm


class SurgeryAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'date', 'users_l', 'procedures_l', 'narrative']
    list_select_related = ('subject',)

    fields = BaseActionAdmin.fields + ['brain_location', 'outcome_type']
    list_display_links = ['date']
    list_filter = [SubjectAliveListFilter,
                   ResponsibleUserListFilter,
                   ('subject__line', RelatedDropdownFilter),
                   ]
    ordering = ['-start_time']

    def date(self, obj):
        return obj.start_time.date()
    date.admin_order_field = 'start_time'

    def users_l(self, obj):
        return ', '.join(map(str, obj.users.all()))
    users_l.short_description = 'users'

    def procedures_l(self, obj):
        return ', '.join(map(str, obj.procedures.all()))
    procedures_l.short_description = 'procedures'

    def get_queryset(self, request):
        return super(SurgeryAdmin, self).get_queryset(request).prefetch_related(
            'users', 'procedures')


class DatasetInline(BaseInlineAdmin):
    model = Dataset
    extra = 1
    fields = ('name', 'dataset_type', 'created_by', 'created_datetime')


class SessionAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'start_time', 'number', 'project_list', 'location', 'user_list']
    list_select_related = ('subject', 'location')
    list_display_links = ['start_time']
    inlines = [NoteInline]
    fields = BaseActionAdmin.fields + ['type', 'number']
    list_filter = [('users', RelatedDropdownFilter),
                   ('start_time', DateRangeFilter),
                   ('subject__projects', RelatedDropdownFilter),
                   ]
    search_fields = ('subject__nickname',)
    ordering = ('-start_time',)
    inlines = [DatasetInline]

    def get_queryset(self, request):
        return super(SessionAdmin, self).get_queryset(request).prefetch_related(
            'subject__projects', 'users')

    def user_list(self, obj):
        return ', '.join(map(str, obj.users.all()))

    def project_list(self, obj):
        return ', '.join(map(str, obj.subject.projects.all()))


admin.site.register(ProcedureType, ProcedureTypeAdmin)
admin.site.register(Weighing, WeighingAdmin)
admin.site.register(WaterAdministration, WaterAdministrationAdmin)
admin.site.register(WaterRestriction, WaterRestrictionAdmin)

admin.site.register(Session, SessionAdmin)
admin.site.register(OtherAction, BaseActionAdmin)
admin.site.register(VirusInjection, BaseActionAdmin)

admin.site.register(Surgery, SurgeryAdmin)
