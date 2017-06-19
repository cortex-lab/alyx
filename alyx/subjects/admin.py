from django import forms
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db.models import Case, When
from django.utils.html import format_html
from django.urls import reverse

from alyx.base import (BaseAdmin, BaseInlineAdmin, DefaultListFilter, MyAdminSite)
from .models import (Allele, BreedingPair, GenotypeTest, Line, Litter, Sequence, Source,
                     Species, Strain, Subject, SubjectRequest, Zygosity, StockManager,
                     )
from actions.models import Surgery, Session, OtherAction
from actions import water
from misc.admin import NoteInline


# Utility functions
# ------------------------------------------------------------------------------------------------

def create_modeladmin(modeladmin, model, name=None):
    # http://stackoverflow.com/a/2228821/1595060
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
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(responsible_user=request.user)
        if self.value() == 'stock':
            sms = [sm.user for sm in StockManager.objects.all()]
            return queryset.filter(responsible_user__in=sms)
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
            return queryset.filter(death_date=None)
        if self.value() == 'n':
            return queryset.exclude(death_date=None)
        elif self.value == 'all':
            return queryset.all()


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
            return queryset.filter(death_date__isnull=False, reduced=False)


class LineDropdownFilter(RelatedDropdownFilter):
    def field_choices(self, field, request, model_admin):
        """Only show active lines in dropdown filters."""
        return field.get_choices(include_blank=False, limit_choices_to={'is_active': True})


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

    def has_add_permission(self, request):
        return False


class AddSurgeryInline(SurgeryInline):
    readonly_fields = ()
    show_change_link = False
    verbose_name = "New surgery"
    verbose_name_plural = "New surgeries"

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request):
        return False


class SessionInline(BaseInlineAdmin):
    model = Session
    extra = 1
    fields = ['procedures', 'narrative', 'start_time',
              'users', 'location']
    classes = ['collapse']


class OtherActionInline(BaseInlineAdmin):
    model = OtherAction
    extra = 1
    fields = ['procedures', 'narrative', 'start_time',
              'users', 'location']
    classes = ['collapse']


def get_admin_url(obj):
    if not obj:
        return '#'
    info = (obj._meta.app_label, obj._meta.model_name)
    return reverse('admin:%s_%s_change' % info, args=(obj.pk,))


class SubjectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        # NOTE: Retrieve the request, passed by ModelAdmin.get_form()
        self.request = kwargs.pop('request', None)
        super(SubjectForm, self).__init__(*args, **kwargs)
        if self.instance.line:
            self.fields['litter'].queryset = Litter.objects.filter(line=self.instance.line)
        self.fields['responsible_user'].queryset = User.objects.all().order_by('username')

    def clean_responsible_user(self):
        old_ru = self.instance.responsible_user
        new_ru = self.cleaned_data['responsible_user']
        logged = self.request.user
        # NOTE: skip the test if the instance is being created
        # such that any user can create a new subject.
        if not self.instance._state.adding and old_ru and new_ru and old_ru != new_ru:
            if (not logged.is_superuser and
                    not StockManager.objects.filter(user=logged) and
                    logged != old_ru):
                raise forms.ValidationError("You are not allowed to change the responsible user.")
        return new_ru


class SubjectAdmin(BaseAdmin):
    fieldsets = (
        ('SUBJECT', {'fields': ('nickname', 'sex', 'birth_date', 'age_days',
                                'responsible_user', 'request', 'wean_date',
                                'to_be_genotyped', 'genotype_date',
                                'death_date', 'to_be_culled',
                                'reduced', 'reduced_date',
                                'ear_mark',
                                'protocol_number', 'description', 'json')}),
        ('PROFILE', {'fields': ('species', 'strain', 'source', 'line', 'litter', 'lamis_cage',),
                     'classes': ('collapse',),
                     }),
        ('OUTCOMES', {'fields': ('cull_method', 'adverse_effects', 'actual_severity'),
                      'classes': ('collapse',),
                      }),
        ('WEIGHINGS/WATER', {'fields': ('last_water_restriction',
                                        'reference_weighing_f',
                                        'current_weighing_f',
                                        'weight_zscore_f',
                                        'implant_weight',
                                        'water_requirement_total_f',
                                        'water_requirement_remaining_f',
                                        'weighing_plot',
                                        ),
                             'classes': ('collapse',),
                             }),
    )

    list_display = ['nickname', 'birth_date', 'sex_l', 'ear_mark_',
                    'breeding_pair_l', 'line_l', 'litter_l',
                    'genotype_l', 'zygosities',
                    'alive', 'responsible_user', 'description'
                    ]
    search_fields = ['nickname',
                     'responsible_user__first_name',
                     'responsible_user__last_name',
                     'responsible_user__username']
    readonly_fields = ('age_days', 'zygosities',
                       'breeding_pair_l', 'litter_l', 'line_l',
                       'last_water_restriction',
                       'reference_weighing_f',
                       'current_weighing_f',
                       'weight_zscore_f',
                       'water_requirement_total_f',
                       'water_requirement_remaining_f',
                       'weighing_plot',
                       )
    ordering = ['-birth_date', '-nickname']
    list_editable = []
    list_filter = [ResponsibleUserListFilter,
                   SubjectAliveListFilter,
                   ZygosityFilter,
                   TodoFilter,
                   ('line', LineDropdownFilter),
                   ]
    form = SubjectForm
    inlines = [ZygosityInline, GenotypeTestInline,
               SurgeryInline, AddSurgeryInline,
               SessionInline, OtherActionInline,
               NoteInline,
               ]

    def ear_mark_(self, obj):
        return obj.ear_mark
    ear_mark_.short_description = 'EM'

    def sex_l(self, obj):
        return obj.sex[0] if obj.sex else ''
    sex_l.short_description = 'sex'

    def genotype_l(self, obj):
        genotype = GenotypeTest.objects.filter(subject=obj)
        return ', '.join(map(str, genotype))
    genotype_l.short_description = 'genotype'

    def breeding_pair_l(self, obj):
        bp = obj.litter.breeding_pair if obj.litter else None
        url = get_admin_url(bp)
        return format_html('<a href="{url}">{breeding_pair}</a>',
                           breeding_pair=bp or '-', url=url)
    breeding_pair_l.short_description = 'BP'

    def litter_l(self, obj):
        url = get_admin_url(obj.litter)
        return format_html('<a href="{url}">{litter}</a>', litter=obj.litter or '-', url=url)
    litter_l.short_description = 'litter'

    def line_l(self, obj):
        url = get_admin_url(obj.line)
        return format_html('<a href="{url}">{line}</a>', line=obj.line or '-', url=url)
    line_l.short_description = 'line'

    def zygosities(self, obj):
        genotype = Zygosity.objects.filter(subject=obj)
        return '; '.join(map(str, genotype))

    def reference_weighing_f(self, obj):
        res = water.reference_weighing(obj)
        return '%.2f' % res.weight if res else '0'
    reference_weighing_f.short_description = 'reference weighing'

    def current_weighing_f(self, obj):
        res = water.current_weighing(obj)
        return '%.2f' % res.weight if res else '0'
    current_weighing_f.short_description = 'current weighing'

    def weight_zscore_f(self, obj):
        res = water.weight_zscore(obj)
        return '%.2f' % res if res else '0'
    weight_zscore_f.short_description = 'weight z-score'

    def water_requirement_total_f(self, obj):
        return '%.2f' % water.water_requirement_total(obj)
    water_requirement_total_f.short_description = 'water requirement total'

    def water_requirement_remaining_f(self, obj):
        return '%.2f' % water.water_requirement_remaining(obj)
    water_requirement_remaining_f.short_description = 'water requirement remaining'

    def weighing_plot(self, obj):
        url = reverse('weighing-plot', kwargs={'subject_id': obj.id})
        return format_html('<img src="{url}" />', url=url)

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
        user = kwargs['request'].user
        if db_field.name == 'responsible_user':
            kwargs['initial'] = user
        return super(SubjectAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'request' and request.resolver_match:
            try:
                parent_obj_id = request.resolver_match.args[0]
                instance = Subject.objects.get(pk=parent_obj_id)
                line = instance.line
                kwargs["queryset"] = SubjectRequest.objects.filter(line=line,
                                                                   user=request.user,
                                                                   )
            except (IndexError, ValidationError):
                pass

        field = super(SubjectAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'line':
            field.queryset = field.queryset.filter(is_active=True)

        return field

    def changelist_view(self, request, extra_context=None):
        """Restrict ability to change responsible user on the subjects list view."""
        if self.__class__.__name__ == 'SubjectAdmin':
            if request.user.is_superuser or StockManager.objects.filter(user=request.user):
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
        self.sequences = line.sequences.all()
        # Set the label of the columns in subject inline.
        for i in range(min(3, len(self.sequences))):
            self.fields['result%d' % i].label = str(self.sequences[i])
        # Set the initial data of the genotype tests for the inline subjects.
        line_seqs = list(line.sequences.all())
        tests = GenotypeTest.objects.filter(subject=subject)
        for test in tests:
            if test.sequence in line_seqs:
                i = line_seqs.index(test.sequence)
                name = 'result%d' % i
                value = test.test_result
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
              'litter', 'lamis_cage',
              'sequence0', 'result0',
              'sequence1', 'result1',
              'sequence2', 'result2',
              'ear_mark', 'description')
    readonly_fields = ('age_weeks', 'alive',
                       'sequence0', 'sequence1', 'sequence2',
                       )
    list_editable = ('lamis_cage',)
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
            sequences = line.sequences.all()
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
    fields = ['descriptive_name', 'breeding_pair', 'birth_date', 'description']
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
    sm = settings.STOCK_MANAGERS
    qs = Subject.objects.filter(line=line, sex=sex,
                                responsible_user__username__in=sm).order_by('nickname')
    ids = [item.id for item in qs]
    qs = Subject.objects.filter(responsible_user__username__in=sm,
                                sex=sex)
    if ids:
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
        qs = qs.order_by(preserved, 'nickname')
    else:
        qs = qs.order_by('nickname')
    return qs


class BreedingPairAdminForm(forms.ModelForm):
    lamis_cage = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super(BreedingPairAdminForm, self).__init__(*args, **kwargs)
        for w in ('father', 'mother1', 'mother2'):
            sex = 'M' if w == 'father' else 'F'
            p = getattr(self.instance, w, None)
            if p and p.lamis_cage:
                self.fields['lamis_cage'].initial = p.lamis_cage
            self.fields[w].queryset = _bp_subjects(self.instance.line, sex)

    def save(self, commit=True):
        lamis_cage = self.cleaned_data.get('lamis_cage')
        if lamis_cage:
            for w in ('father', 'mother1', 'mother2'):
                p = getattr(self.instance, w, None)
                if p:
                    p.lamis_cage = int(lamis_cage)
                    p.save()
        return super(BreedingPairAdminForm, self).save(commit=commit)

    class Meta:
        fields = '__all__'
        model = BreedingPair


class BreedingPairAdmin(BaseAdmin):
    form = BreedingPairAdminForm
    list_display = ['name', 'lamis_cage', 'line_l', 'start_date', 'end_date',
                    'father_l', 'mother1_l', 'mother2_l']
    fields = ['name', 'line', 'start_date', 'end_date',
              'father', 'mother1', 'mother2', 'lamis_cage', 'description']
    list_filter = [BreedingPairFilter,
                   ('line', LineDropdownFilter),
                   ]
    inlines = [LitterInline]

    def lamis_cage(self, obj):
        return obj.father.lamis_cage if obj.father else None

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
        if self.instance.line:
            self.fields['breeding_pair'].queryset = BreedingPair.objects.filter(
                line=self.instance.line,
            )


class LitterAdmin(BaseAdmin):
    list_display = ['descriptive_name', 'breeding_pair', 'birth_date']
    fields = ['line', 'descriptive_name',
              'breeding_pair', 'birth_date',
              'description',
              ]
    list_filter = [('line', LineDropdownFilter),
                   ]
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
    model = Line.sequences.through
    extra = 1
    fields = ['sequence']


class BreedingPairInline(BaseInlineAdmin):
    model = BreedingPair
    fields = ('line', 'name', 'father', 'mother1', 'mother2')
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


class LineAdmin(BaseAdmin):
    fields = ['name', 'auto_name', 'target_phenotype', 'is_active',
              'strain', 'species', 'description',
              'subject_autoname_index',
              'breeding_pair_autoname_index',
              'litter_autoname_index',
              ]
    list_display = ['name', 'auto_name', 'target_phenotype', 'strain', 'is_active']
    ordering = ['auto_name']
    list_filter = [LineFilter]
    list_editable = ['is_active']

    inlines = [SubjectRequestInline, SubjectInline, SequencesInline, BreedingPairInline]

    def get_formsets_with_inlines(self, request, obj=None, *args, **kwargs):
        # Make the parent instance accessible from the inline admin.
        # http://stackoverflow.com/a/24427952/1595060
        for inline in self.get_inline_instances(request, obj):
            inline._parent_instance = obj
            yield inline.get_formset(request, obj), inline

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        return super(LineAdmin, self).get_form(request, obj, **kwargs)

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
        self.fields['user'].queryset = User.objects.all().order_by('username')


class SubjectRequestAdmin(BaseAdmin):
    fields = ['line', 'count', 'date_time', 'due_date', 'description', 'user',
              'subjects_l', 'remaining', 'status']
    list_display = ['line', 'user', 'remaining_count', 'date_time', 'due_date', 'is_closed']
    readonly_fields = ['subjects_l', 'status', 'remaining', 'remaining_count']
    list_filter = [SubjectRequestUserListFilter,
                   SubjectRequestStatusListFilter,
                   ('line', LineDropdownFilter),
                   ]
    inlines = [SubjectInlineNonEditable]

    form = SubjectRequestForm

    def remaining_count(self, obj):
        return '%d/%d' % ((obj.count or 0) - (obj.remaining() or 0), obj.count or 0)
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
            return self.readonly_fields + ['binomial']
        return self.readonly_fields

    fields = ['binomial', 'display_name']
    list_display = ['binomial', 'display_name']
    readonly_fields = []


class StrainAdmin(BaseAdmin):
    fields = ['descriptive_name', 'description']


class AlleleAdmin(BaseAdmin):
    fields = ['standard_name', 'informal_name']


class SourceAdmin(BaseAdmin):
    fields = ['name', 'description']


class SequenceAdmin(BaseAdmin):
    fields = ['base_pairs', 'informal_name', 'description']


class MyUserAdmin(UserAdmin):
    ordering = ['username']
    list_display = ['username', 'email', 'first_name', 'last_name',
                    'groups_l',
                    'is_staff', 'is_superuser',
                    ]

    def groups_l(self, obj):
        return ', '.join(map(str, obj.groups.all()))
    groups_l.short_description = 'groups'


class StockManagerAdmin(BaseAdmin):
    fields = ['user']


# Reorganize admin index
# ------------------------------------------------------------------------------------------------

mysite = MyAdminSite()
mysite.site_header = 'Alyx'
mysite.site_title = 'Alyx'
mysite.site_url = None
mysite.index_title = 'Welcome to Alyx'

admin.site = mysite

mysite.register(User, MyUserAdmin)
mysite.register(StockManager, StockManagerAdmin)
mysite.register(Group)

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

mysite.register(GenotypeTest)
mysite.register(Zygosity)


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
            return queryset.filter(death_date=None)
        if self.value() == 'n':
            return queryset.exclude(death_date=None)
        if self.value() == 'nr':
            return queryset.filter(reduced=False).exclude(death_date=None)
        if self.value() == 'tbc':
            return queryset.filter(to_be_culled=True, death_date=None)
        elif self.value == 'all':
            return queryset.all()


class CullMiceAdmin(SubjectAdmin):
    list_display = ['nickname', 'birth_date', 'sex_f',
                    'ear_mark', 'line', 'zygosities',
                    'lamis_cage', 'responsible_user',
                    'death_date', 'to_be_culled', 'reduced',
                    ]
    ordering = ['-birth_date', '-nickname']
    list_filter = [ResponsibleUserListFilter,
                   CullSubjectAliveListFilter,
                   ('line', LineDropdownFilter),
                   ]
    list_editable = ['death_date', 'to_be_culled', 'reduced']

    def sex_f(self, obj):
        return obj.sex[0] if obj.sex else ''
    sex_f.short_description = 'sex'

    def has_add_permission(self, request):
        return False


create_modeladmin(SubjectAdverseEffectsAdmin, model=Subject, name='Adverse effect')
create_modeladmin(CullMiceAdmin, model=Subject, name='Cull subject')
