import base64
import json
import logging

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Case, When
from django.urls import reverse
from django.utils.html import format_html
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from django.contrib.admin import TabularInline
from rangefilter.filter import DateRangeFilter

from alyx.base import (BaseAdmin, DefaultListFilter, BaseInlineAdmin, get_admin_url)
from .models import (OtherAction, ProcedureType, Session, EphysSession, Surgery, VirusInjection,
                     WaterAdministration, WaterRestriction, Weighing, WaterType,
                     Notification, NotificationRule, Cull, CullReason, CullMethod,
                     )
from data.models import Dataset, FileRecord
from misc.admin import NoteInline
from subjects.models import Subject
from .water_control import WaterControl
from experiments.models import ProbeInsertion

logger = logging.getLogger(__name__)


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
            return queryset.filter(subject__cull__isnull=True)
        if self.value() == 'n':
            return queryset.exclude(subject__cull__isnull=True)
        elif self.value == 'all':
            return queryset.all()


class ActiveFilter(DefaultListFilter):
    title = 'active'
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        return (
            (None, 'All'),
            ('active', 'Active'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(start_time__isnull=False,
                                   end_time__isnull=True,
                                   )
        elif self.value is None:
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
            self.fields['users'].queryset = get_user_model().objects.all().order_by('username')
        if 'user' in self.fields:
            self.fields['user'].queryset = get_user_model().objects.all().order_by('username')
        if 'subject' in self.fields:
            inst = self.instance
            ids = [s.id for s in Subject.objects.filter(responsible_user=self.current_user,
                                                        cull__isnull=True).order_by('nickname')]
            if getattr(inst, 'subject', None):
                ids = _bring_to_front(ids, inst.subject.pk)
            if getattr(self, 'last_subject_id', None):
                ids = _bring_to_front(ids, self.last_subject_id)
            # These ids first in the list of subjects.
            if ids:
                preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
                self.fields['subject'].queryset = Subject.objects.filter(
                    cull__isnull=True).order_by(preserved, 'nickname')
            else:
                self.fields['subject'].queryset = Subject.objects.filter(
                    cull__isnull=True).order_by('nickname')


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

    def projects(self, obj):
        return ', '.join(p.name for p in obj.subject.projects.all())

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
                subject = Subject.objects.filter(id=subject_id).first()
                if subject:
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
        # These ids first in the list of subjects, if any ids
        if not self.fields:
            return
        elif ids:
            preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
            self.fields['subject'].queryset = Subject.objects.order_by(preserved, 'nickname')
        else:
            self.fields['subject'].queryset = Subject.objects.order_by('nickname')
        self.fields['user'].queryset = get_user_model().objects.all().order_by('username')
        self.fields['water_administered'].widget.attrs.update({'autofocus': 'autofocus'})


class WaterAdministrationAdmin(BaseActionAdmin):
    form = WaterAdministrationForm

    fields = ['subject', 'date_time', 'water_administered', 'water_type', 'adlib', 'user',
              'session_l']
    list_display = ['subject_l', 'water_administered', 'user', 'date_time', 'water_type',
                    'adlib', 'session_l', 'projects']
    list_display_links = ('water_administered', )
    list_select_related = ('subject', 'user')
    ordering = ['-date_time', 'subject__nickname']
    search_fields = ['subject__nickname', 'subject__projects__name']
    list_filter = [ResponsibleUserListFilter, ('subject', RelatedDropdownFilter)]
    readonly_fields = ['session_l', ]

    def session_l(self, obj):
        url = get_admin_url(obj.session)
        return format_html('<a href="{url}">{session}</a>', session=obj.session or '-', url=url)
    session_l.short_description = 'Session'
    session_l.allow_tags = True


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
            kwargs['queryset'] = Subject.objects.filter(cull__isnull=True).order_by('nickname')
            subject_id = self._get_last_subject(request)
            if subject_id:
                subject = Subject.objects.get(id=subject_id)
                kwargs['initial'] = subject
        return super(BaseActionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super(WaterRestrictionAdmin, self).get_form(request, obj, **kwargs)
        subject = getattr(obj, 'subject', None)
        iw = getattr(subject, 'implant_weight', None)
        rw = subject.water_control.weight() if subject else None
        form.base_fields['implant_weight'].initial = iw or 0
        if self.has_change_permission(request, obj):
            form.base_fields['reference_weight'].initial = rw or 0
        return form

    form = WaterRestrictionForm

    fields = ['subject', 'implant_weight', 'reference_weight',
              'start_time', 'end_time', 'water_type', 'users', 'narrative']
    list_display = ('subject_w', 'start_time_l', 'end_time_l', 'water_type', 'weight',
                    'weight_ref') + WaterControl._columns[3:] + ('projects',)
    list_select_related = ('subject',)
    list_display_links = ('start_time_l', 'end_time_l')
    readonly_fields = ('weight',)  # WaterControl._columns[1:]
    ordering = ['-start_time', 'subject__nickname']
    search_fields = ['subject__nickname', 'subject__projects__name']
    list_filter = [ResponsibleUserListFilter,
                   ('subject', RelatedDropdownFilter),
                   ActiveFilter,
                   ]

    def subject_w(self, obj):
        url = reverse('water-history', kwargs={'subject_id': obj.subject.id})
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.subject.nickname)
    subject_w.short_description = 'subject'
    subject_w.admin_order_field = 'subject'

    def start_time_l(self, obj):
        return obj.start_time.date()
    start_time_l.short_description = 'start date'
    start_time_l.admin_order_field = 'start_time'

    def end_time_l(self, obj):
        if obj.end_time:
            return obj.end_time.date()
        else:
            return obj.end_time
    end_time_l.short_description = 'end date'
    end_time_l.admin_order_field = 'end_time'

    def weight(self, obj):
        if not obj.subject:
            return
        return '%.1f' % obj.subject.water_control.weight()
    weight.short_description = 'weight'

    def weight_ref(self, obj):
        if not obj.subject:
            return
        return '%.1f' % obj.subject.water_control.reference_weight()

    def expected_weight(self, obj):
        if not obj.subject:
            return
        return '%.1f' % obj.subject.water_control.expected_weight()
    expected_weight.short_description = 'weight exp'

    def percentage_weight(self, obj):
        if not obj.subject:
            return
        return '%.1f' % obj.subject.water_control.percentage_weight()
    percentage_weight.short_description = 'weight pct'

    def min_weight(self, obj):
        if not obj.subject:
            return
        return '%.1f' % obj.subject.water_control.min_weight()
    min_weight.short_description = 'weight min'

    def given_water_reward(self, obj):
        if not obj.subject:
            return
        return '%.2f' % obj.subject.water_control.given_water_reward()
    given_water_reward.short_description = 'water reward'

    def given_water_supplement(self, obj):
        if not obj.subject:
            return
        return '%.2f' % obj.subject.water_control.given_water_supplement()
    given_water_supplement.short_description = 'water suppl'

    def given_water_total(self, obj):
        if not obj.subject:
            return
        return '%.2f' % obj.subject.water_control.given_water_total()
    given_water_total.short_description = 'water tot'

    def expected_water(self, obj):
        if not obj.subject:
            return
        return '%.2f' % obj.subject.water_control.expected_water()
    expected_water.short_description = 'water exp'

    def excess_water(self, obj):
        if not obj.subject:
            return
        return '%.2f' % obj.subject.water_control.excess_water()
    excess_water.short_description = 'water excess'

    def is_water_restricted(self, obj):
        return obj.is_active()
    is_water_restricted.short_description = 'is active'
    is_water_restricted.boolean = True


class WeighingForm(BaseActionForm):
    def __init__(self, *args, **kwargs):
        super(WeighingForm, self).__init__(*args, **kwargs)
        if self.fields.keys():
            self.fields['weight'].widget.attrs.update({'autofocus': 'autofocus'})


class WeighingAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'weight', 'percentage_weight', 'date_time', 'projects']
    list_select_related = ('subject',)
    fields = ['subject', 'date_time', 'weight', 'user']
    ordering = ('-date_time',)
    list_display_links = ('weight',)
    search_fields = ['subject__nickname', 'subject__projects__name']
    list_filter = [ResponsibleUserListFilter,
                   ('subject', RelatedDropdownFilter)]

    form = WeighingForm

    def percentage_weight(self, obj):
        wc = obj.subject.water_control
        return wc.percentage_weight_html(date=obj.date_time)
    percentage_weight.short_description = 'Weight %'


class WaterTypeAdmin(BaseActionAdmin):
    list_display = ['name', 'json']
    fields = ['name', 'json']
    ordering = ('name',)
    list_display_links = ('name',)


class SurgeryAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'date', 'users_l', 'procedures_l', 'narrative', 'projects']
    list_select_related = ('subject',)

    fields = BaseActionAdmin.fields + ['outcome_type']
    list_display_links = ['date']
    search_fields = ('subject__nickname', 'subject__projects__name')
    list_filter = [SubjectAliveListFilter,
                   ResponsibleUserListFilter,
                   ('subject__line', RelatedDropdownFilter),
                   ]
    ordering = ['-start_time']
    inlines = [NoteInline]

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
    show_change_link = True
    model = Dataset
    extra = 1
    fields = ('name', 'dataset_type', 'collection', '_online', 'version', 'created_by',
              'created_datetime')
    readonly_fields = fields
    ordering = ("name",)

    def _online(self, obj):
        return obj.online
    _online.short_description = 'On server'
    _online.boolean = True


class WaterAdminInline(BaseInlineAdmin):
    model = WaterAdministration
    extra = 0
    fields = ('name', 'water_administered', 'water_type')
    readonly_fields = ('name', 'water_administered', 'water_type')


def _pass_narrative_templates(context):
    context['narrative_templates'] = \
        base64.b64encode(json.dumps(settings.NARRATIVE_TEMPLATES).encode('utf-8')).decode('utf-8')
    return context


class SessionAdmin(BaseActionAdmin):
    list_display = ['subject_l', 'start_time', 'number', 'lab', 'dataset_count',
                    'task_protocol', 'qc', 'user_list', 'project_']
    list_display_links = ['start_time']
    fields = BaseActionAdmin.fields + [
        'repo_url', 'qc', 'extended_qc', 'project', ('type', 'task_protocol', ), 'number',
        'n_correct_trials', 'n_trials', 'weighing']
    list_filter = [('users', RelatedDropdownFilter),
                   ('start_time', DateRangeFilter),
                   ('project', RelatedDropdownFilter),
                   ('lab', RelatedDropdownFilter),
                   ('subject__projects', RelatedDropdownFilter)
                   ]
    search_fields = ('subject__nickname', 'lab__name', 'project__name', 'users__username',
                     'task_protocol')
    ordering = ('-start_time', 'task_protocol', 'lab')
    inlines = [WaterAdminInline, DatasetInline, NoteInline]
    readonly_fields = ['repo_url', 'task_protocol', 'weighing', 'qc', 'extended_qc']

    def get_form(self, request, obj=None, **kwargs):
        from subjects.admin import Project
        from django.db.models import Q
        form = super(SessionAdmin, self).get_form(request, obj, **kwargs)
        if form.base_fields and not request.user.is_superuser:
            # the projects edit box is limited to projects with no user or containing current user
            current_proj = obj.project.pk if obj and obj.project else None
            form.base_fields['project'].queryset = Project.objects.filter(
                Q(users=request.user.pk) | Q(users=None) | Q(pk=current_proj)
            ).distinct()
        return form

    def change_view(self, request, object_id, extra_context=None, **kwargs):
        context = extra_context or {}
        context = _pass_narrative_templates(context)
        return super(SessionAdmin, self).change_view(
            request, object_id, extra_context=context, **kwargs)

    def add_view(self, request, extra_context=None):
        context = extra_context or {}
        context = _pass_narrative_templates(context)
        return super(SessionAdmin, self).add_view(request, extra_context=context)

    def project_(self, obj):
        return getattr(obj.project, 'name', None)

    def repo_url(self, obj):
        url = settings.SESSION_REPO_URL.format(
            lab=obj.subject.lab.name,
            subject=obj.subject.nickname,
            date=obj.start_time.date(),
            number=obj.number or 0,
        )
        return format_html(
            '<a href="{url}">{url}</a>'.format(url=url))

    def user_list(self, obj):
        return ', '.join(map(str, obj.users.all()))
    user_list.short_description = 'users'

    def dataset_count(self, ses):
        cs = FileRecord.objects.filter(dataset__in=ses.data_dataset_session_related.all(),
                                       data_repository__globus_is_personal=False,
                                       exists=True).values_list('relative_path').distinct().count()
        cr = FileRecord.objects.filter(dataset__in=ses.data_dataset_session_related.all(),
                                       ).values_list('relative_path').distinct().count()
        if cr == 0:
            return '-'
        col = '008000' if cr == cs else '808080'  # green if all files uploaded on server
        return format_html('<b><a style="color: #{};">{}</a></b>', col, '{:2.0f}'.format(cr))
    dataset_count.short_description = '# datasets'
    dataset_count.admin_order_field = '_dataset_count'

    def weighing(self, obj):
        wei = Weighing.objects.filter(date_time=obj.start_time)
        if not wei:
            return ''
        url = reverse('admin:%s_%s_change' % (wei[0]._meta.app_label, wei[0]._meta.model_name),
                      args=[wei[0].id])
        return format_html('<b><a href="{url}" ">{} g </a></b>', wei[0].weight, url=url)
    weighing.short_description = 'weight before session'


class ProbeInsertionInline(TabularInline):
    fk_name = "session"
    show_change_link = True
    model = ProbeInsertion
    fields = ('name', 'model')
    extra = 0


class EphysSessionAdmin(SessionAdmin):
    inlines = [ProbeInsertionInline, WaterAdminInline, DatasetInline, NoteInline]

    def get_queryset(self, request):
        qs = super(EphysSessionAdmin, self).get_queryset(request)
        return qs.filter(task_protocol__icontains='ephys')


class NotificationUserFilter(DefaultListFilter):
    title = 'notification users'
    parameter_name = 'users'

    def lookups(self, request, model_admin):
        return (
            (None, 'Me'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(users__in=[request.user])
        elif self.value == 'all':
            return queryset.all()


class NotificationAdmin(BaseAdmin):
    list_display = ('title', 'subject', 'users_l',
                    'send_at', 'sent_at',
                    'status', 'notification_type')
    search_fields = ('notification_type', 'subject__nickname', 'title')
    list_filter = (NotificationUserFilter, 'notification_type')
    fields = ('title', 'notification_type', 'subject', 'message',
              'users', 'status', 'send_at', 'sent_at')
    ordering = ('-send_at',)

    def users_l(self, obj):
        return sorted(map(str, obj.users.all()))


class NotificationRuleAdmin(BaseAdmin):
    list_display = ('notification_type', 'user', 'subjects_scope')
    search_fields = ('notification_type', 'user__username', 'subject_scope')
    fields = ('notification_type', 'user', 'subjects_scope')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user':
            kwargs['initial'] = request.user.id
        return super(NotificationRuleAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )


class CullAdmin(BaseAdmin):
    list_display = ('date', 'subject_l', 'user', 'cull_reason', 'cull_method', 'projects')
    search_fields = ('user__username', 'subject__nickname', 'subject__projects__name')
    fields = ('date', 'subject', 'user', 'cull_reason', 'cull_method', 'description')
    ordering = ('-date',)

    def subject_l(self, obj):
        url = get_admin_url(obj.subject)
        return format_html('<a href="{url}">{subject}</a>', subject=obj.subject or '-', url=url)
    subject_l.short_description = 'subject'

    def projects(self, obj):
        return ', '.join(p.name for p in obj.subject.projects.all())


admin.site.register(ProcedureType, ProcedureTypeAdmin)
admin.site.register(Weighing, WeighingAdmin)
admin.site.register(WaterAdministration, WaterAdministrationAdmin)
admin.site.register(WaterRestriction, WaterRestrictionAdmin)

admin.site.register(Session, SessionAdmin)
admin.site.register(EphysSession, EphysSessionAdmin)
admin.site.register(OtherAction, BaseActionAdmin)
admin.site.register(VirusInjection, BaseActionAdmin)

admin.site.register(Surgery, SurgeryAdmin)
admin.site.register(WaterType, WaterTypeAdmin)

admin.site.register(Notification, NotificationAdmin)
admin.site.register(NotificationRule, NotificationRuleAdmin)

admin.site.register(Cull, CullAdmin)
admin.site.register(CullReason, BaseAdmin)
admin.site.register(CullMethod, BaseAdmin)
