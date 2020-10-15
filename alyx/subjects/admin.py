from django import forms
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Case, When, Count, Prefetch
from django.forms import BaseInlineFormSet
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q

from alyx.base import (BaseAdmin, BaseInlineAdmin, DefaultListFilter, get_admin_url,
                       _iter_history_changes)
from .models import (Allele, BreedingPair, GenotypeTest, Line, Litter, Sequence, Source,
                     Species, Strain, Subject, SubjectRequest, Zygosity, ZygosityRule,
                     Project,
                     )
from actions.models import (
    Surgery, Session, OtherAction, WaterAdministration, WaterRestriction, Weighing)
from misc.models import LabMember, Housing
from misc.admin import NoteInline


# Utility functions
# ------------------------------------------------------------------------------------------------

def create_modeladmin(modeladmin, model, name=None):
    # http://stackoverflow.com/a/2228821/1595060
    name = name.replace(' ', '_')

    class Meta:
        proxy = True
        app_label = model._meta.app_label
    attrs = {'__module__': '', 'Meta': Meta}
    newmodel = type(name, (model,), attrs)
    newmodel.Meta.verbose_name_plural = name
    admin.site.register(newmodel, modeladmin)
    return modeladmin


# Filters
# ------------------------------------------------------------------------------------------------

class ResponsibleUserListFilter(DefaultListFilter):
    title = 'responsible user'
    parameter_name = 'responsible_user'

    def lookups(self, request, model_admin):
        return (
            (None, 'Me'),
            ('all', 'All'),
            ('stock', 'Stock'),
            ('nostock', 'No stock'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            qs = queryset.filter(responsible_user=request.user)
            if qs.count() == 0:
                qs = queryset.all()
            return qs
        if self.value() == 'stock':
            return queryset.filter(responsible_user__is_stock_manager=True)
        elif self.value() == 'nostock':
            return queryset.filter(responsible_user__is_stock_manager=False)
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
            return queryset.filter(cull__isnull=True)
        if self.value() == 'n':
            return queryset.exclude(cull__isnull=True)
        elif self.value == 'all':
            return queryset.all()


class BreederListFilter(DefaultListFilter):
    title = 'breeder'
    parameter_name = 'breeder'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            (None, 'No'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value == 'all':
            return queryset.all()
        bp = BreedingPair.objects.filter(start_date__isnull=False,
                                         end_date__isnull=True,
                                         )
        f = bp.filter(father__isnull=False).values_list('father', flat=True)
        m1 = bp.filter(mother1__isnull=False).values_list('mother1', flat=True)
        m2 = bp.filter(mother2__isnull=False).values_list('mother2', flat=True)
        subjects = f.union(m1, m2)
        if self.value() is None:
            return queryset.exclude(pk__in=subjects)
        elif self.value() == 'yes':
            return queryset.filter(pk__in=subjects)


class ZygosityFilter(DefaultListFilter):
    title = 'zygosity'
    parameter_name = 'zygosity'

    def lookups(self, request, model_admin):
        return (
            (None, 'All'),
            ('p', 'All positive'),
            ('h', 'All homo'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.all()
        elif self.value() in ('p', 'h'):
            # Only keep subjects with a non-null geontype.
            queryset = queryset.filter(genotype__isnull=False).distinct()
            # Exclude subjects that have a specific zygosity/
            d = dict(zygosity=0) if self.value() == 'p' else dict(zygosity__in=(0, 1, 3))
            nids = set([z.subject.id.hex for z in Zygosity.objects.filter(**d)])
            return queryset.exclude(pk__in=nids)


class TodoFilter(DefaultListFilter):
    title = 'todo'
    parameter_name = 'todo'

    def lookups(self, request, model_admin):
        return (
            (None, 'All'),
            ('g', 'To be genotyped'),
            ('c', 'To be culled'),
            ('r', 'To be reduced'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.all()
        elif self.value() == 'g':
            return queryset.filter(to_be_genotyped=True)
        elif self.value() == 'c':
            return queryset.filter(to_be_culled=True)
        elif self.value() == 'r':
            return queryset.filter(cull__isnull=False, reduced=False)


class LineDropdownFilter(RelatedDropdownFilter):
    def field_choices(self, field, request, model_admin):
        """Only show active lines in dropdown filters."""
        return field.get_choices(include_blank=False, limit_choices_to={'is_active': True})


# Project
# ------------------------------------------------------------------------------------------------

class ProjectAdmin(BaseAdmin):
    fields = ('name', 'description', 'users')
    list_display = ('name', 'subjects_count', 'sessions_count', 'users_l')

    def users_l(self, obj):
        return ', '.join(map(str, obj.users.all()))
    users_l.short_description = 'users'

    def sessions_count(self, obj):
        return Session.objects.filter(project=obj).count()
    sessions_count.short_description = '# sessions'

    def subjects_count(self, obj):
        return Subject.objects.filter(projects=obj).count()
    subjects_count.short_description = '# subjects'


# Subject
# ------------------------------------------------------------------------------------------------

class ZygosityInline(BaseInlineAdmin):
    model = Zygosity
    extra = 1
    fields = ['allele', 'zygosity']
    classes = ['collapse']


class GenotypeTestInline(BaseInlineAdmin):
    model = GenotypeTest
    extra = 1
    fields = ['sequence', 'test_result']
    classes = ['collapse']


class SurgeryInline(BaseInlineAdmin):
    model = Surgery
    extra = 1
    fields = ['procedures', 'narrative', 'start_time', 'end_time', 'outcome_type',
              'users', 'location']
    readonly_fields = fields
    classes = ['collapse']
    show_change_link = True
    can_delete = False
    verbose_name = "Past surgery"
    verbose_name_plural = "Past surgeries"
    ordering = ('-start_time',)

    def has_add_permission(self, request, obj=None):
        return False


class AddSurgeryInline(SurgeryInline):
    readonly_fields = ()
    show_change_link = False
    verbose_name = "New surgery"
    verbose_name_plural = "New surgeries"

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return False


class HousingInline(admin.TabularInline):
    model = Housing.subjects.through
    extra = 0
    exclude = ('name', 'json',)

    def get_queryset(self, request):
        qs = super(HousingInline, self).get_queryset(request)
        return qs.filter(end_datetime__isnull=True)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "housing" and request._obj_:
            from django.db.models import Q
            kwargs["queryset"] = Housing.objects.filter(
                Q(subjects__isnull=True) |
                Q(housing_subjects__subject__lab__in=[request._obj_.lab])
            ).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SessionInline(BaseInlineAdmin):
    model = Session
    extra = 1
    fields = ['procedures', 'narrative', 'start_time', 'users', 'location']
    readonly_fields = fields
    classes = ['collapse']
    ordering = ('-start_time',)


class OtherActionInline(BaseInlineAdmin):
    model = OtherAction
    extra = 1
    fields = ['procedures', 'narrative', 'start_time',
              'users', 'location']
    classes = ['collapse']
    ordering = ('-start_time',)


class SubjectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        # NOTE: Retrieve the request, passed by ModelAdmin.get_form()
        self.request = kwargs.pop('request', None)
        super(SubjectForm, self).__init__(*args, **kwargs)
        if not self.fields:
            return
        if self.instance.line:
            self.fields['litter'].queryset = Litter.objects.filter(line=self.instance.line)
        self.fields['responsible_user'].queryset = get_user_model().objects.all()
        if not self.request.user.is_superuser:
            # the projects edit box is limited to projects with no user or containing current user
            self.fields['projects'].queryset = Project.objects.filter(
                Q(users=self.request.user.pk) | Q(users=None)
            )

    def clean_responsible_user(self):
        old_ru = self.instance.responsible_user
        new_ru = self.cleaned_data['responsible_user']
        logged = self.request.user
        # NOTE: skip the test if the instance is being created
        # such that any user can create a new subject.
        if not self.instance._state.adding and old_ru and new_ru and old_ru != new_ru:
            if (not logged.is_superuser and not logged.is_stock_manager and
                    logged != old_ru):
                raise forms.ValidationError("You are not allowed to change the responsible user.")
        return new_ru


class SubjectAdmin(BaseAdmin):
    HOUSING_FIELDS = ('housing_l', 'cage_name', 'cage_type', 'light_cycle', 'enrichment',
                      'food', 'cage_mates_l')
    fieldsets = (
        ('SUBJECT', {'fields': ('nickname', 'sex', 'birth_date', 'age_days', 'responsible_user',
                                'request', 'wean_date',
                                ('to_be_genotyped', 'genotype_date',),
                                ('death_date', 'to_be_culled'),
                                ('reduced_date', 'reduced'),
                                ('cull_', 'cull_reason_'),
                                'ear_mark',
                                'protocol_number', 'description',
                                'lab', 'projects', 'json', 'subject_history')}),
        ('HOUSING (read-only, edit widget at the bottom of the page)',
         {'fields': HOUSING_FIELDS, 'classes': ('extrapretty',), }),
        ('PROFILE', {'fields': ('species', 'strain', 'source', 'line', 'litter',
                                'cage', 'cage_changes',),
                     'classes': ('collapse',),
                     }),
        ('OUTCOMES', {'fields': ('cull_method', 'adverse_effects', 'actual_severity'),
                      'classes': ('collapse',),
                      }),
        ('WEIGHINGS/WATER', {'fields': ('implant_weight',
                                        'current_weight',
                                        'reference_weight',
                                        'expected_weight',
                                        'given_water',
                                        'expected_water',
                                        'remaining_water',
                                        'water_history_link',
                                        'weighing_plot',
                                        ),
                             'classes': ('collapse',),
                             }),
    )

    list_display = ['nickname', 'weight_percent', 'birth_date', 'sex_l', 'alive', 'session_count',
                    'responsible_user', 'lab', 'description',
                    'project_l',  # 'session_projects_l',
                    'ear_mark_', 'line_l', 'litter_l', 'zygosities', 'cage', 'breeding_pair_l',
                    ]
    search_fields = ['nickname',
                     'responsible_user__first_name',
                     'responsible_user__last_name',
                     'responsible_user__username',
                     'cage',
                     'lab__name',
                     'projects__name',
                     ]
    readonly_fields = ('age_days', 'zygosities', 'subject_history',
                       'breeding_pair_l', 'litter_l', 'line_l',
                       'cage_changes', 'cull_', 'cull_reason_',
                       'death_date',
                       ) + fieldsets[4][1]['fields'][1:] + HOUSING_FIELDS  # water read only fields
    ordering = ['-birth_date', '-nickname']
    list_editable = []
    list_filter = [ResponsibleUserListFilter,
                   SubjectAliveListFilter,
                   BreederListFilter,
                   ZygosityFilter,
                   TodoFilter,
                   ('line', LineDropdownFilter),
                   ]
    form = SubjectForm
    inlines = [ZygosityInline, GenotypeTestInline,
               SurgeryInline,
               AddSurgeryInline,
               SessionInline,
               OtherActionInline,
               NoteInline,
               HousingInline,
               ]

    def get_queryset(self, request):
        q = super(SubjectAdmin, self).get_queryset(request).select_related(
            'request', 'request__user', 'litter', 'litter__breeding_pair',
            'responsible_user',
            'line', 'lab', 'cull', 'cull__cull_method', 'cull__cull_reason',
            'species', 'strain', 'source',
        ).prefetch_related(
            'zygosity_set',
            'zygosity_set__allele',
            'line__alleles',
            Prefetch(
                'actions_waterrestrictions',
                queryset=WaterRestriction.objects.order_by('start_time')),
            Prefetch(
                'water_administrations',
                queryset=WaterAdministration.objects.order_by('date_time')),
            Prefetch(
                'weighings',
                queryset=Weighing.objects.order_by('date_time')),
        )
        q = q.annotate(sessions_count=Count('actions_sessions'))
        return q

    def session_projects_l(self, sub):
        return ', '.join(sub.session_projects)
    session_projects_l.short_description = 'session proj'

    def session_count(self, sub):
        return sub.sessions_count
    session_count.short_description = '# sess'

    def weight_percent(self, sub):
        wc = sub.water_control
        return wc.percentage_weight_html()
    weight_percent.short_description = 'Weight %'

    def ear_mark_(self, obj):
        return obj.ear_mark
    ear_mark_.short_description = 'EM'

    def sex_l(self, obj):
        return obj.sex[0] if obj.sex else ''
    sex_l.short_description = 'sex'

    def breeding_pair_l(self, obj):
        bp = obj.litter.breeding_pair if obj.litter else None
        url = get_admin_url(bp)
        return format_html('<a href="{url}">{breeding_pair}</a>',
                           breeding_pair=bp or '-', url=url)
    breeding_pair_l.short_description = 'BP'

    def cull_reason_(self, obj):
        if hasattr(obj, 'cull'):
            return obj.cull.cull_reason
    cull_reason_.short_description = 'cull reason'

    def cull_(self, obj):
        if not hasattr(obj, 'cull'):
            return
        url = get_admin_url(obj.cull)
        return format_html('<a href="{url}">{cull}</a>', cull=obj.cull or '-', url=url)
    cull_.short_description = 'cull object'

    def housing_l(self, obj):
        url = get_admin_url(obj.housing)
        return format_html('<a href="{url}">{housing}</a>', housing=obj.housing or '-', url=url)
    housing_l.short_description = 'housing'

    def cage_mates_l(self, obj):
        if obj.cage_mates:
            return ','.join(list(obj.cage_mates.values_list('nickname', flat=True)))
    cage_mates_l.short_description = 'cage mates'

    def litter_l(self, obj):
        url = get_admin_url(obj.litter)
        return format_html('<a href="{url}">{litter}</a>', litter=obj.litter or '-', url=url)
    litter_l.short_description = 'litter'

    def line_l(self, obj):
        url = get_admin_url(obj.line)
        return format_html('<a href="{url}">{line}</a>', line=obj.line or '-', url=url)
    line_l.short_description = 'line'

    def project_l(self, obj):
        # url = get_admin_url(obj.line)
        # return format_html('<a href="{url}">{line}</a>', line=obj.line or '-', url=url)
        return '\n'.join(list(obj.projects.all().values_list('name', flat=True)))
    project_l.short_description = 'projects'

    def zygosities(self, obj):
        return '; '.join(obj.zygosity_strings())

    def reference_weight(self, obj):
        res = obj.water_control.reference_weighing_at()
        return '%.2f' % res[1] if res else '0'

    def current_weight(self, obj):
        res = obj.water_control.current_weighing()
        return '%.2f' % res[1] if res else '0'

    def expected_weight(self, obj):
        res = obj.water_control.expected_weight()
        return '%.2f' % res if res else '0'

    def expected_water(self, obj):
        return '%.2f' % obj.water_control.expected_water()

    def given_water(self, obj):
        return '%.2f' % obj.water_control.given_water()

    def remaining_water(self, obj):
        return '%.2f' % obj.water_control.remaining_water()

    def weighing_plot(self, obj):
        if not obj or not obj.id:
            return
        url = reverse('weighing-plot', kwargs={'subject_id': obj.id})
        return format_html('<img src="{url}" />', url=url)

    def water_history_link(self, obj):
        if not obj or not obj.id:
            return
        url = reverse('water-history', kwargs={'subject_id': obj.id})
        return format_html('<a href="{url}">Go to the water history page</a>', url=url)

    def subject_history(self, obj):
        if not obj or not obj.id:
            return
        url = reverse('subject-history', kwargs={'subject_id': obj.id})
        return format_html('<a href="{url}">Go to the subject history page</a>', url=url)

    def cage_changes(self, obj):
        return format_html('<br />\n'.join(_iter_history_changes(obj, 'cage')))

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj

        # NOTE: make the request available in the form
        # http://stackoverflow.com/a/9191583/1595060
        form = super(SubjectAdmin, self).get_form(request, obj, **kwargs)

        class AdminFormWithRequest(form):
            def __new__(cls, *args, **kwargs):
                kwargs['request'] = request
                return form(*args, **kwargs)

        return AdminFormWithRequest

    def formfield_for_dbfield(self, db_field, **kwargs):
        request = kwargs['request']
        user = request.user
        formfield = super(SubjectAdmin, self).formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'responsible_user':
            kwargs['initial'] = user
            choices = getattr(request, '_responsible_user_choices_cache', None)
            if choices is None:
                request._responsible_user_choices_cache = choices = list(formfield.choices)
            formfield.choices = choices
        return formfield

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'request' and request.resolver_match:
            try:
                parent_obj_id = request.resolver_match.args[0]
                instance = Subject.objects.get(pk=parent_obj_id)
                line = instance.line
                kwargs["queryset"] = SubjectRequest.objects.filter(
                    line=line, user=request.user)
            except (IndexError, ValidationError):
                pass

        field = super(SubjectAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'line':
            field.queryset = field.queryset.filter(is_active=True)

        return field

    def changelist_view(self, request, extra_context=None):
        """Restrict ability to change responsible user on the subjects list view."""
        if self.__class__.__name__ == 'SubjectAdmin':
            if request.user.is_superuser or request.user.is_stock_manager:
                self.list_editable = ['responsible_user']
            else:
                self.list_editable = []
        return super(SubjectAdmin, self).changelist_view(request, extra_context)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        # Default user is the logged user.
        obj = formset.instance
        line = obj.line
        if obj.responsible_user is None:
            obj.responsible_user = request.user
        # Set the line of all inline litters.
        for instance in instances:
            if isinstance(instance, Litter):
                instance.line = line
            instance.save()
        formset.save_m2m()

    def save_model(self, request, obj, form, change):
        if obj.reduced_date is not None and not obj.reduced:
            obj.reduced = True
        if hasattr(obj, 'cull') and obj.to_be_culled:
            obj.to_be_culled = False
        super(SubjectAdmin, self).save_model(request, obj, form, change)


# Subject inline
# ------------------------------------------------------------------------------------------------


class SubjectInlineForm(forms.ModelForm):
    TEST_RESULTS = (
        ('', '----'),
        (0, 'Absent'),
        (1, 'Present'),
    )
    result0 = forms.ChoiceField(choices=TEST_RESULTS, required=False)
    result1 = forms.ChoiceField(choices=TEST_RESULTS, required=False)
    result2 = forms.ChoiceField(choices=TEST_RESULTS, required=False)

    class Meta:
        model = Subject
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(SubjectInlineForm, self).__init__(*args, **kwargs)
        self.sequences = []
        subject = self.instance
        line = subject.line
        if not line:
            return
        self.sequences = line.sequences
        # Set the label of the columns in subject inline.
        for i in range(min(3, len(self.sequences))):
            self.fields['result%d' % i].label = str(self.sequences[i])
        # Set the initial data of the genotype tests for the inline subjects.
        line_seqs = list(line.sequences)
        tests = GenotypeTest.objects.filter(subject=subject)
        for test in tests:
            if test.sequence in line_seqs:
                i = line_seqs.index(test.sequence)
                name = 'result%d' % i
                value = test.test_result
                if name in self.fields:
                    self.fields[name].initial = value

    def save(self, commit=True):
        # Save the genotype tests.
        for i in range(min(3, len(self.sequences))):
            sequence = self.sequences[i]
            result = self.cleaned_data.get('result%d' % i, '')
            if result == '':
                res = GenotypeTest.objects.filter(subject=self.instance, sequence=sequence)
                res.delete()
            elif result in ('0', '1'):
                result = int(result)
                res = GenotypeTest.objects.filter(subject=self.instance, sequence=sequence)
                if not res:
                    test = GenotypeTest(subject=self.instance, sequence=sequence,
                                        test_result=result)
                    test.save()
                else:
                    test = res[0]
                    test.test_result = result
                    test.save()
        return super(SubjectInlineForm, self).save(commit=commit)


class SubjectInline(BaseInlineAdmin):
    model = Subject
    extra = 1
    fields = ('nickname', 'birth_date', 'alive', 'wean_date', 'genotype_date', 'to_be_genotyped',
              'age_weeks', 'sex', 'line',
              'litter', 'cage',
              'sequence0', 'result0',
              'sequence1', 'result1',
              'sequence2', 'result2',
              'ear_mark', 'description')
    readonly_fields = ('age_weeks', 'alive',
                       'sequence0', 'sequence1', 'sequence2',
                       )
    list_editable = ('cage',)
    show_change_link = True
    form = SubjectInlineForm
    _parent_instance = None

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # Filter breeding_pairs by breeding_pairs that are part of that line.
        field = super(SubjectInline, self).formfield_for_foreignkey(db_field,
                                                                    request, **kwargs)

        if db_field.name == 'breeding_pair':
            if isinstance(request._obj_, Line):
                field.queryset = field.queryset.filter(line=request._obj_)
            elif isinstance(request._obj_, Litter):
                field.queryset = field.queryset.filter(line=request._obj_.line)
            else:
                field.queryset = field.queryset.none()

        return field

    def _get_sequence(self, obj, i):
        if isinstance(self._parent_instance, Line):
            line = self._parent_instance
        elif isinstance(self._parent_instance, Litter):
            line = self._parent_instance.line
        elif isinstance(self._parent_instance, BreedingPair):
            line = self._parent_instance.line
        else:
            line = None
        if line:
            sequences = line.sequences
            if i < len(sequences):
                return sequences[i]

    def alive(self, obj):
        return obj.alive()
    alive.boolean = True

    def sequence0(self, obj):
        return self._get_sequence(obj, 0)

    def sequence1(self, obj):
        return self._get_sequence(obj, 1)

    def sequence2(self, obj):
        return self._get_sequence(obj, 2)

    def result0(self, obj):
        return

    def result1(self, obj):
        return

    def result2(self, obj):
        return


# BreedingPair
# ------------------------------------------------------------------------------------------------

class LitterInline(BaseInlineAdmin):
    model = Litter
    fields = ['name', 'breeding_pair', 'birth_date', 'description']
    extra = 1
    show_change_link = True

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(LitterInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

        if db_field.name == ('breeding_pair'):
            if request._obj_ is not None:
                field.queryset = field.queryset.filter(line=request._obj_.line)
            else:
                field.queryset = field.queryset.none()

        return field


class BreedingPairFilter(DefaultListFilter):
    title = 'status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            (None, 'Current'),
            ('p', 'Past'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(start_date__isnull=False, end_date=None)
        if self.value() == 'p':
            return queryset.filter(start_date__isnull=False, end_date__isnull=False)
        elif self.value == 'all':
            return queryset.all()


def _bp_subjects(line, sex):
    # All alive subjects of the given sex.
    qs = Subject.objects.filter(
        sex=sex, responsible_user__is_stock_manager=True, cull__isnull=True)
    qs = qs.order_by('nickname')
    ids = [item.id for item in qs]
    if ids:
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
        qs = qs.order_by(preserved, 'nickname')
    else:
        qs = qs.order_by('nickname')
    return qs


class BreedingPairAdminForm(forms.ModelForm):
    cage = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super(BreedingPairAdminForm, self).__init__(*args, **kwargs)
        for w in ('father', 'mother1', 'mother2'):
            sex = 'M' if w == 'father' else 'F'
            p = getattr(self.instance, w, None)
            if p and p.cage:
                self.fields['cage'].initial = p.cage
            if w in self.fields:
                self.fields[w].queryset = _bp_subjects(self.instance.line, sex)

    def save(self, commit=True):
        cage = self.cleaned_data.get('cage')
        if cage:
            for w in ('father', 'mother1', 'mother2'):
                p = getattr(self.instance, w, None)
                if p:
                    p.cage = int(cage)
                    p.save()
        return super(BreedingPairAdminForm, self).save(commit=commit)

    class Meta:
        fields = '__all__'
        model = BreedingPair


class BreedingPairAdmin(BaseAdmin):
    form = BreedingPairAdminForm
    list_display = ['name', 'cage', 'line_l', 'start_date', 'end_date',
                    'father_l', 'mother1_l', 'mother2_l']
    list_select_related = ('line', 'father', 'mother1', 'mother2')
    fields = ['name', 'line', 'start_date', 'end_date',
              'father', 'mother1', 'mother2', 'cage', 'description']
    # NOTE: disabling autocomplete fields here because of a django bug:
    # https://code.djangoproject.com/ticket/29707
    # autocomplete_fields = ('father', 'mother1', 'mother2')
    list_filter = [BreedingPairFilter,
                   ('line', LineDropdownFilter),
                   ]
    inlines = [LitterInline]

    def cage(self, obj):
        for _ in ('father', 'mother1', 'mother2'):
            parent = getattr(obj, _, None)
            if parent and parent.cage:
                return parent.cage

    def line_l(self, obj):
        url = get_admin_url(obj.line)
        return format_html('<a href="{url}">{line}</a>', line=obj.line or '-', url=url)
    line_l.short_description = 'line'

    def father_l(self, obj):
        url = get_admin_url(obj.father)
        return format_html('<a href="{url}">{name}</a>',
                           name=obj.father.nickname if obj.father else '-', url=url)
    father_l.short_description = 'father'

    def mother1_l(self, obj):
        url = get_admin_url(obj.mother1)
        return format_html('<a href="{url}">{name}</a>',
                           name=obj.mother1.nickname if obj.mother1 else '-', url=url)
    mother1_l.short_description = 'mother1'

    def mother2_l(self, obj):
        url = get_admin_url(obj.mother2)
        return format_html('<a href="{url}">{name}</a>',
                           name=obj.mother2.nickname if obj.mother2 else '-', url=url)
    mother2_l.short_description = 'mother2'

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        return super(BreedingPairAdmin, self).get_form(request, obj, **kwargs)

    def get_formsets_with_inlines(self, request, obj=None, *args, **kwargs):
        # Make the parent instance accessible from the inline admin.
        # http://stackoverflow.com/a/24427952/1595060
        for inline in self.get_inline_instances(request, obj):
            inline._parent_instance = obj
            yield inline.get_formset(request, obj), inline

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        obj = formset.instance
        line = obj.line
        # Set the line of all inline litters.
        for instance in instances:
            if isinstance(instance, Litter):
                instance.line = line
            elif isinstance(instance, Subject):
                # Default user is the logged user.
                if instance.responsible_user is None:
                    instance.responsible_user = request.user
            instance.save()
        formset.save_m2m()


# Litter
# ------------------------------------------------------------------------------------------------

class LitterForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(LitterForm, self).__init__(*args, **kwargs)
        if self.instance.line and 'breeding_pair' in self.fields:
            self.fields['breeding_pair'].queryset = BreedingPair.objects.filter(
                line=self.instance.line,
            )


class LitterAdmin(BaseAdmin):
    list_display = ['name', 'breeding_pair', 'birth_date']
    list_select_related = ('breeding_pair',)
    fields = ['line', 'name',
              'breeding_pair', 'birth_date',
              'description',
              ]
    list_filter = [('line', LineDropdownFilter),
                   ]
    search_fields = ['name']
    form = LitterForm

    inlines = [SubjectInline]

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        return super(LitterAdmin, self).get_form(request, obj, **kwargs)

    def get_formsets_with_inlines(self, request, obj=None, *args, **kwargs):
        # Make the parent instance accessible from the inline admin.
        # http://stackoverflow.com/a/24427952/1595060
        for inline in self.get_inline_instances(request, obj):
            inline._parent_instance = obj
            yield inline.get_formset(request, obj), inline

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        obj = formset.instance
        # obj is a Litter instance.
        bp = obj.breeding_pair
        father = bp.father if bp else None
        to_copy = 'species,strain,source'.split(',')
        user = (father.responsible_user
                if father and father.responsible_user else request.user)
        for instance in instances:
            # Copy the birth date and breeding_pair from the litter.
            instance.breeding_pair = bp
            instance.line = obj.line
            instance.birth_date = obj.birth_date
            if instance.responsible_user is None:
                instance.responsible_user = user
            # Copy some fields from the mother to the subject.
            for field in to_copy:
                setattr(instance, field, getattr(father, field, None))
            instance.save()
        formset.save_m2m()


# Line
# ------------------------------------------------------------------------------------------------

class SubjectRequestInline(BaseInlineAdmin):
    model = SubjectRequest
    extra = 1
    fields = ['count', 'due_date', 'status', 'description']
    readonly_fields = ['status']


class SequencesInline(BaseInlineAdmin):
    model = Allele.sequences.through
    extra = 1
    fields = ['sequence']


class AllelesInline(BaseInlineAdmin):
    model = Line.alleles.through
    extra = 1
    fields = ['allele']


class BreedingPairFormset(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super(BreedingPairFormset, self).__init__(*args, **kwargs)


class BreedingPairInline(BaseInlineAdmin):
    model = BreedingPair
    formset = BreedingPairFormset
    fields = ('line', 'name', 'father', 'mother1', 'mother2')
    autocomplete_fields = ('father', 'mother1', 'mother2')
    readonly_fields = ()
    extra = 1

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(BreedingPairInline, self).formfield_for_foreignkey(db_field,
                                                                         request, **kwargs)
        obj = self._parent_instance
        if obj is None:
            return field
        if db_field.name in ('father', 'mother1', 'mother2'):
            sex = 'M' if db_field.name == 'father' else 'F'
            field.queryset = _bp_subjects(obj, sex)
        return field


class LineFilter(DefaultListFilter):
    title = 'active lines'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            (None, 'Active'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(is_active=True)
        elif self.value == 'all':
            return queryset.all()


class LineForm(forms.ModelForm):
    bsu_strain_code = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super(LineForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        bsu_strain_code = self.cleaned_data.get('bsu_strain_code', None)
        if self.instance:
            if not self.instance.json:
                self.instance.json = {}
            if bsu_strain_code or self.instance.json.get('bsu_strain_code', None):
                self.instance.json['bsu_strain_code'] = bsu_strain_code
        return super(LineForm, self).save(commit=commit)

    class Meta:
        model = Line
        fields = '__all__'


class LineAdmin(BaseAdmin):
    form = LineForm

    fields = ['name', 'nickname', 'target_phenotype', 'is_active',
              'strain', 'species', 'description',
              'subject_autoname_index',
              'breeding_pair_autoname_index',
              'litter_autoname_index',
              'source', 'source_identifier',
              'bsu_strain_code',
              'source_url', 'expression_data_url'
              ]
    list_display = ['name', 'nickname', 'target_phenotype', 'strain', 'bsu_strain_code',
                    'source_link', 'expression', 'is_active']
    list_select_related = ('strain',)
    ordering = ['nickname']
    list_filter = [LineFilter]
    list_editable = ['is_active']
    search_fields = ('nickname',)

    inlines = [SubjectRequestInline, AllelesInline, BreedingPairInline]

    def source_link(self, obj):
        return format_html('<a href="{source_url}">{source_text}</a>',
                           source_url=obj.source_url or '#',
                           source_text='%s %s' % (obj.source, obj.source_identifier)
                           if obj.source else '')
    source_link.short_description = 'source'

    def expression(self, obj):
        e = obj.expression_data_url
        if not e:
            return
        t = e[:12] + '...'
        return format_html('<a href="{expression_url}">{expression_text}</a>',
                           expression_url=e,
                           expression_text=t,
                           )

    def bsu_strain_code(self, obj):
        return (obj.json or {}).get('bsu_strain_code', None)

    def get_formsets_with_inlines(self, request, obj=None, *args, **kwargs):
        # Make the parent instance accessible from the inline admin.
        # http://stackoverflow.com/a/24427952/1595060
        for inline in self.get_inline_instances(request, obj):
            inline._parent_instance = obj
            yield inline.get_formset(request, obj), inline

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        form = super(LineAdmin, self).get_form(request, obj, **kwargs)
        if obj:
            bsu_strain_code = (obj.json or {}).get('bsu_strain_code', None)
            form.base_fields['bsu_strain_code'].initial = bsu_strain_code
        return form

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        line = formset.instance
        for instance in instances:
            if isinstance(instance, Subject):
                # Copy some fields from the line to the subject.
                for field in ('species', 'strain'):
                    value = getattr(line, field, None)
                    if value:
                        setattr(instance, field, value)
                # Default user is the logged user.
                if instance.responsible_user is None:
                    instance.responsible_user = request.user
            elif isinstance(instance, SubjectRequest):
                # Copy some fields from the line to the instanceect.
                instance.user = request.user
            instance.save()
        formset.save_m2m()


# Subject request
# ------------------------------------------------------------------------------------------------

class SubjectRequestStatusListFilter(DefaultListFilter):
    title = 'status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            (None, 'Open'),
            ('c', 'Closed'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        instances = queryset.all()
        if self.value() is None:
            pks = [obj.pk for obj in instances if obj.status() == 'Open']
            return SubjectRequest.objects.filter(pk__in=pks)
        if self.value() == 'c':
            pks = [obj.pk for obj in instances if obj.status() == 'Closed']
            return SubjectRequest.objects.filter(pk__in=pks)
        elif self.value == 'all':
            return queryset.all()


class SubjectRequestUserListFilter(DefaultListFilter):
    title = 'user'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        return (
            (None, 'Me'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(user=request.user)
        elif self.value == 'all':
            return queryset.all()


class SubjectInlineNonEditable(SubjectInline):
    readonly_fields = SubjectInline.fields


class SubjectRequestForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(SubjectRequestForm, self).__init__(*args, **kwargs)
        self.fields['user'].queryset = get_user_model().objects.all().order_by('username')


class SubjectRequestAdmin(BaseAdmin):
    fields = ['line', 'count', 'date_time', 'due_date', 'description', 'user',
              'subjects_l', 'remaining', 'status']
    list_display = ['line', 'user', 'remaining_count', 'date_time', 'due_date', 'is_closed']
    list_select_related = ('line', 'user')
    readonly_fields = ['subjects_l', 'status', 'remaining', 'remaining_count']
    list_filter = [SubjectRequestUserListFilter,
                   SubjectRequestStatusListFilter,
                   ('line', LineDropdownFilter),
                   ]
    inlines = [SubjectInlineNonEditable]

    form = SubjectRequestForm

    def remaining_count(self, obj):
        c = obj.count or 0
        r = obj.remaining() or 0
        return '%d/%d' % (c - r, c)
    remaining_count.short_description = 'count'

    def is_closed(self, obj):
        return obj.status() == 'Closed'
    is_closed.boolean = True

    def subjects_l(self, obj):
        return format_html('; '.join('<a href="{url}">{subject}</a>'.format(
                                     subject=subject or '-',
                                     url=get_admin_url(subject))
                                     for subject in obj.subjects()))
    subjects_l.short_description = 'subjects'

    def get_queryset(self, request):
        return super(SubjectRequestAdmin, self).get_queryset(request).prefetch_related(
            'subject_set')

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        return super(SubjectRequestAdmin, self).get_form(request, obj, **kwargs)

    def formfield_for_dbfield(self, db_field, **kwargs):
        user = kwargs['request'].user
        if db_field.name == 'user':
            kwargs['initial'] = user
        return super(SubjectRequestAdmin, self).formfield_for_dbfield(db_field, **kwargs)


# Other
# ------------------------------------------------------------------------------------------------

class SpeciesAdmin(BaseAdmin):

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['name']
        return self.readonly_fields

    fields = ['name', 'nickname']
    list_display = ['name', 'nickname']
    readonly_fields = []


class StrainAdmin(BaseAdmin):
    fields = ['name', 'description']


class AlleleAdmin(BaseAdmin):
    fields = ['nickname', 'name']
    search_fields = fields

    inlines = [SequencesInline]


class SourceAdmin(BaseAdmin):
    fields = ['name', 'description']


class SequenceAdmin(BaseAdmin):
    fields = ['base_pairs', 'name', 'description']
    search_fields = fields


class ZygosityRuleAdmin(BaseAdmin):
    fields = ('line', 'allele', 'sequence0', 'sequence0_result',
              'sequence1', 'sequence1_result', 'zygosity')
    list_display = fields
    list_editable = fields[2:]
    ordering = ('line', 'allele', 'sequence0', 'sequence1')
    list_filter = (('line', RelatedDropdownFilter), ('allele', RelatedDropdownFilter))
    list_select_related = ('line', 'allele', 'sequence0', 'sequence1')


class ZygosityAdmin(BaseAdmin):
    fields = ('subject', 'allele', 'zygosity')
    list_display = fields
    list_editable = ('allele', 'zygosity')
    ordering = ('subject', 'allele')
    search_fields = ('subject__nickname', 'allele__name')
    list_filter = (('allele', RelatedDropdownFilter),)
    list_select_related = ('subject', 'allele')


class GenotypeTestAdmin(BaseAdmin):
    fields = ('subject', 'sequence', 'test_result')
    list_display = fields
    list_editable = ('sequence', 'test_result')
    ordering = ('subject', 'sequence')
    search_fields = ('subject__nickname', 'sequence__name')
    list_filter = (('sequence', RelatedDropdownFilter),)
    list_select_related = ('subject', 'sequence')


class LabMemberAdminForm(UserChangeForm):
    class Meta:
        fields = ('__all__')
        model = LabMember

    def clean(self):
        current_user = LabMember.objects.get(pk=self.request_user.pk)
        if self.request_user != self.instance and not current_user.is_superuser:
            raise forms.ValidationError("You can't change other users.")
        return super(LabMemberAdminForm, self).clean()


class LabMemberAdmin(UserAdmin):
    form = LabMemberAdminForm

    fieldsets = UserAdmin.fieldsets + (
        ('Extra fields', {'fields': ('allowed_users',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra fields', {'fields': ('allowed_users',)}),
    )

    ordering = ['username']
    list_display = ['username', 'email', 'first_name', 'last_name',
                    'groups_l', 'allowed_users_',
                    'is_staff', 'is_superuser', 'is_stock_manager',
                    ]
    list_editable = ['is_stock_manager']
    save_on_top = True

    def get_form(self, request, obj=None, **kwargs):
        form = super(LabMemberAdmin, self).get_form(request, obj, **kwargs)
        form.request_user = request.user
        return form

    def groups_l(self, obj):
        return ', '.join(map(str, obj.groups.all()))
    groups_l.short_description = 'groups'

    def allowed_users_(self, obj):
        return ', '.join(u.username for u in obj.allowed_users.all())
    allowed_users_.short_description = 'allowed users'


# Reorganize admin index
# ------------------------------------------------------------------------------------------------

mysite = admin.site

mysite.register(LabMember, LabMemberAdmin)
mysite.register(Group)

mysite.register(Project, ProjectAdmin)
mysite.register(Subject, SubjectAdmin)
mysite.register(Litter, LitterAdmin)
mysite.register(Line, LineAdmin)
mysite.register(BreedingPair, BreedingPairAdmin)

mysite.register(SubjectRequest, SubjectRequestAdmin)
mysite.register(Species, SpeciesAdmin)
mysite.register(Strain, StrainAdmin)
mysite.register(Source, SourceAdmin)
mysite.register(Allele, AlleleAdmin)
mysite.register(Sequence, SequenceAdmin)

mysite.register(GenotypeTest, GenotypeTestAdmin)
mysite.register(Zygosity, ZygosityAdmin)
mysite.register(ZygosityRule, ZygosityRuleAdmin)

# Alternative admin views
# ------------------------------------------------------------------------------------------------


class SubjectAdverseEffectsAdmin(SubjectAdmin):
    list_display = ['nickname', 'responsible_user', 'sex', 'birth_date',
                    'death_date', 'ear_mark', 'line_l', 'actual_severity',
                    'adverse_effects', 'cull_method']
    ordering = ['-birth_date']
    list_filter = [SubjectAliveListFilter,
                   ResponsibleUserListFilter,
                   ]
    list_editable = []

    def cull_method(self, obj):
        if obj.cull:
            return obj.cull.cull_method

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return (self.model.objects.
                exclude(adverse_effects__isnull=True).
                exclude(adverse_effects__exact='')
                )

    def line_l(self, obj):
        # obj is the Subject instance, obj.line is the subject's Line instance.
        url = get_admin_url(obj.line)  # url to the Change line page
        return format_html('<a href="{url}">{line}</a>', line=obj.line or '-', url=url)
    line_l.short_description = 'line'


class CullSubjectAliveListFilter(DefaultListFilter):
    title = 'alive'
    parameter_name = 'alive'

    def lookups(self, request, model_admin):
        return (
            (None, 'Yes'),
            ('n', 'No'),
            ('nr', 'Not reduced'),
            ('tbc', 'To be culled'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(cull__isnull=True)
        if self.value() == 'n':
            return queryset.exclude(cull__isnull=True)
        if self.value() == 'nr':
            return queryset.filter(reduced=False).exclude(cull__isnull=True)
        if self.value() == 'tbc':
            return queryset.filter(to_be_culled=True, cull__isnull=True)
        elif self.value == 'all':
            return queryset.all()


class CullMiceAdmin(SubjectAdmin):
    list_display = ['nickname', 'birth_date', 'death_date', 'sex_f', 'ear_mark',
                    'line', 'cage', 'responsible_user', 'to_be_culled', 'reduced', 'cull_l']
    ordering = ['-birth_date', '-nickname']
    list_filter = [ResponsibleUserListFilter,
                   CullSubjectAliveListFilter,
                   ('line', LineDropdownFilter),
                   ]
    list_editable = ['death_date', 'to_be_culled', 'reduced']

    ordering = ('-birth_date',)

    def sex_f(self, obj):
        return obj.sex[0] if obj.sex else ''
    sex_f.short_description = 'sex'

    def has_add_permission(self, request):
        return False

    def cull_l(self, obj):
        if hasattr(obj, 'cull'):
            url = get_admin_url(obj.cull)
            return format_html('<a href="{url}">{cull}</a>', cull=obj.cull.date or '-', url=url)
    cull_l.short_description = 'cull'


create_modeladmin(SubjectAdverseEffectsAdmin, model=Subject, name='Adverse effect')
create_modeladmin(CullMiceAdmin, model=Subject, name='Cull subject')
