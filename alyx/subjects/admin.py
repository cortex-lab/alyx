from django import forms
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.template.response import TemplateResponse
from alyx.base import BaseAdmin, BaseInlineAdmin
from .models import *
from actions.models import Surgery, Experiment, OtherAction


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

class DefaultListFilter(admin.SimpleListFilter):
    # Default filter value.
    # http://stackoverflow.com/a/16556771/1595060
    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == lookup,
                'query_string': cl.get_query_string({
                    self.parameter_name: lookup,
                }, []),
                'display': title,
            }


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
            return queryset.filter(responsible_user=request.user)
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


# Subject
# ------------------------------------------------------------------------------------------------

class ZygosityInline(BaseInlineAdmin):
    model = Zygosity
    extra = 2
    fields = ['allele', 'zygosity']


class GenotypeTestInline(BaseInlineAdmin):
    model = GenotypeTest
    extra = 2
    fields = ['sequence', 'test_result']


class SurgeryInline(BaseInlineAdmin):
    model = Surgery
    extra = 1
    fields = ['brain_location', 'procedures', 'narrative', 'start_time',
              'users', 'location']


class ExperimentInline(BaseInlineAdmin):
    model = Experiment
    extra = 1
    fields = ['procedures', 'narrative', 'start_time',
              'users', 'location']


class OtherActionInline(BaseInlineAdmin):
    model = OtherAction
    extra = 1
    fields = ['procedures', 'narrative', 'start_time',
              'users', 'location']


def get_admin_url(obj):
    if not obj:
        return '#'
    info = (obj._meta.app_label, obj._meta.model_name)
    return reverse('admin:%s_%s_change' % info, args=(obj.pk,))


class SubjectAdmin(BaseAdmin):
    fieldsets = (
        ('SUBJECT', {'fields': ('nickname', 'sex', 'birth_date', 'age_days', 'cage',
                                'responsible_user', 'request', 'wean_date',
                                'death_date', 'ear_mark',
                                'protocol_number', 'notes', 'json')}),
        ('PROFILE', {'fields': ('species', 'strain', 'source', 'line', 'litter')}),
        ('OUTCOMES', {'fields': ('cull_method', 'adverse_effects', 'actual_severity')}),
        ('WEIGHINGS/WATER', {'fields': ('water_restriction_date',
                                        'reference_weighing_f',
                                        'current_weighing_f',
                                        'implant_weight',
                                        'water_requirement_total_f',
                                        'water_requirement_remaining_f',
                                        'weighing_plot',
                                        )}),
    )

    list_display = ['nickname', 'birth_date', 'sex_l', 'ear_mark',
                    'cage_l', 'line_l', 'litter_l',
                    'genotype_l', 'zygosities',
                    'alive', 'responsible_user',
                    ]
    search_fields = ['nickname',
                     'responsible_user__first_name',
                     'responsible_user__last_name',
                     'responsible_user__username']
    readonly_fields = ('age_days', 'zygosities',
                       'cage_l', 'litter_l', 'line_l',
                       'water_restriction_date',
                       'reference_weighing_f',
                       'current_weighing_f',
                       'water_requirement_total_f',
                       'water_requirement_remaining_f',
                       'weighing_plot',
                       )
    ordering = ['-birth_date', 'nickname']
    list_editable = ['responsible_user']
    list_filter = [SubjectAliveListFilter, ResponsibleUserListFilter, 'line']
    inlines = [ZygosityInline, GenotypeTestInline,
               SurgeryInline, ExperimentInline, OtherActionInline]

    def sex_l(self, obj):
        return obj.sex[0] if obj.sex else ''
    sex_l.short_description = 'sex'

    def genotype_l(self, obj):
        genotype = GenotypeTest.objects.filter(subject=obj)
        return ', '.join(map(str, genotype))
    genotype_l.short_description = 'genotype'

    def cage_l(self, obj):
        url = get_admin_url(obj.cage)
        return format_html('<a href="{url}">{cage}</a>', cage=obj.cage or '-', url=url)
    cage_l.short_description = 'cage'

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
        return '%.2f' % obj.reference_weighing()
    reference_weighing_f.short_description = 'reference weighing'

    def current_weighing_f(self, obj):
        return '%.2f' % obj.current_weighing()
    current_weighing_f.short_description = 'current weighing'

    def water_requirement_total_f(self, obj):
        return '%.2f' % obj.water_requirement_total()
    water_requirement_total_f.short_description = 'water requirement total'

    def water_requirement_remaining_f(self, obj):
        return '%.2f' % obj.water_requirement_remaining()
    water_requirement_remaining_f.short_description = 'water requirement remaining'

    def weighing_plot(self, obj):
        url = reverse('weighing-plot', kwargs={'subject_id': obj.id})
        return format_html('<img src="{url}" />', url=url)

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        return super(SubjectAdmin, self).get_form(request, obj, **kwargs)

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
            except IndexError:
                pass
        return super(SubjectAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

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
        formset.instance.save()
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
    fields = ('nickname', 'birth_date', 'wean_date', 'age_weeks', 'sex', 'line', 'cage',
              'litter', 'mother', 'father',
              'sequence0', 'result0',
              'sequence1', 'result1',
              'sequence2', 'result2',
              'ear_mark', 'notes')
    readonly_fields = ('age_weeks', 'mother', 'father',
                       'sequence0', 'sequence1', 'sequence2',
                       )
    show_change_link = True
    form = SubjectInlineForm
    _parent_instance = None

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # Filter cages by cages that are part of that line.
        field = super(SubjectInline, self).formfield_for_foreignkey(db_field,
                                                                    request, **kwargs)

        if db_field.name == 'cage':
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
        elif isinstance(self._parent_instance, Cage):
            line = self._parent_instance.line
        else:
            line = None
        if line:
            sequences = line.sequences.all()
            if i < len(sequences):
                return sequences[i]

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


# Cage
# ------------------------------------------------------------------------------------------------

class LitterInline(BaseInlineAdmin):
    model = Litter
    fields = ['descriptive_name', 'mother', 'father', 'birth_date', 'notes']
    extra = 1
    show_change_link = True

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(LitterInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

        if db_field.name in ('mother', 'father'):
            if request._obj_ is not None:
                field.queryset = field.queryset.filter(line=request._obj_.line)
            else:
                field.queryset = field.queryset.none()

        return field


class CageAdminForm(forms.ModelForm):
    class Meta:
        fields = '__all__'
        model = Cage


class CageAdmin(BaseAdmin):
    form = CageAdminForm
    list_display = ['cage_label', 'line', 'location']
    fields = ('line', 'cage_label', 'type', 'location')
    list_filter = ['line']
    inlines = [SubjectInline, LitterInline]

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        return super(CageAdmin, self).get_form(request, obj, **kwargs)

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

class LitterAdmin(BaseAdmin):
    list_display = ['descriptive_name', 'mother', 'father', 'birth_date']
    fields = ['line', 'descriptive_name',
              'mother', 'father', 'birth_date',
              'notes', 'cage']

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
        line = obj.line
        mother = obj.mother
        to_copy = 'species,strain,line,source'.split(',')
        user = (obj.mother.responsible_user
                if obj.mother and obj.mother.responsible_user else request.user)
        for instance in instances:
            # Copy the birth date and cage from the litter.
            instance.birth_date = obj.birth_date
            instance.cage = obj.cage
            instance.responsible_user = user
            # Copy some fields from the mother to the subject.
            for field in to_copy:
                setattr(instance, field, getattr(mother, field, None))
            instance.save()
        formset.save_m2m()


# Line
# ------------------------------------------------------------------------------------------------

class SubjectRequestInline(BaseInlineAdmin):
    model = SubjectRequest
    extra = 1
    fields = ['count', 'due_date', 'status', 'notes']
    readonly_fields = ['status']


class SequencesInline(BaseInlineAdmin):
    model = Line.sequences.through
    extra = 1
    fields = ['sequence']


class CageInline(BaseInlineAdmin):
    model = Cage
    fields = ('line', 'cage_label', 'type', 'location')
    extra = 1


class LineAdmin(BaseAdmin):
    fields = ['name', 'auto_name', 'target_phenotype', 'strain', 'species', 'description',
              'subject_autoname_index',
              'cage_autoname_index',
              'litter_autoname_index',
              ]
    list_display = ['name', 'auto_name', 'target_phenotype', 'strain']

    inlines = [SubjectRequestInline, SubjectInline, SequencesInline, CageInline]

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


class SubjectRequestAdmin(BaseAdmin):
    fields = ['line', 'count', 'date_time', 'due_date', 'notes', 'user',
              'subjects_l', 'remaining', 'status']
    list_display = ['line', 'user', 'remaining_count', 'date_time', 'due_date', 'is_closed']
    readonly_fields = ['subjects_l', 'status', 'remaining', 'remaining_count']
    list_filter = ['line', SubjectRequestUserListFilter, SubjectRequestStatusListFilter]

    def remaining_count(self, obj):
        return '%d/%d' % (obj.count - obj.remaining(), obj.count)
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
    fields = ['name', 'notes']


class SequenceAdmin(BaseAdmin):
    fields = ['base_pairs', 'informal_name', 'description']


# Reorganize admin index
# ------------------------------------------------------------------------------------------------

class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


flatten = lambda l: [item for sublist in l for item in sublist]


class MyAdminSite(admin.AdminSite):
    def index(self, request, extra_context=None):

        order = [('Common', ['Subjects',
                             'Surgeries',
                             'Lines',
                             'Cages',
                             'Litters',
                             'Virus injections',
                             'Water restrictions',
                             'Other actions',
                             'Subject requests',
                             ]),
                 ('Static', ['Procedure types',
                             'Species',
                             'Strains',
                             'Alleles',
                             'Sequences',
                             'Sources',
                             ]),
                 ('Other', ['Experiments',
                            'Water administrations',
                            'Weighings',
                            'Genotype tests',
                            'Zygosities',
                            ]),
                 ('IT admin', ['Tokens',
                               'Groups',
                               'Users',
                               ]),
                 ]
        extra_in_common = ['Adverse effects', 'Cull subjects']
        order_models = flatten([models for app, models in order])
        app_list = self.get_app_list(request)
        models_dict = {str(model['name']): model
                       for app in app_list
                       for model in app['models']}
        model_to_app = {str(model['name']): str(app['name'])
                        for app in app_list
                        for model in app['models']}
        category_list = [Bunch(name=name, models=[models_dict[m] for m in model_names])
                         for name, model_names in order]
        for model_name, app_name in model_to_app.items():
            if model_name in order_models:
                continue
            if model_name.startswith('Subject') or model_name in extra_in_common:
                category_list[0].models.append(models_dict[model_name])
            elif app_name == 'Equipment':
                category_list[1].models.append(models_dict[model_name])
            else:
                category_list[2].models.append(models_dict[model_name])
        context = dict(
            self.each_context(request),
            title=self.index_title,
            app_list=category_list,
        )
        context.update(extra_context or {})
        request.current_app = self.name

        return TemplateResponse(request, self.index_template or 'admin/index.html', context)


mysite = MyAdminSite()
admin.site = mysite
admin.site.register(User)
admin.site.register(Group)

admin.site.register(Subject, SubjectAdmin)
admin.site.register(Litter, LitterAdmin)
admin.site.register(Line, LineAdmin)
admin.site.register(Cage, CageAdmin)

admin.site.register(SubjectRequest, SubjectRequestAdmin)
admin.site.register(Species, SpeciesAdmin)
admin.site.register(Strain, StrainAdmin)
admin.site.register(Source, SourceAdmin)
admin.site.register(Allele, AlleleAdmin)
admin.site.register(Sequence, SequenceAdmin)

admin.site.register(GenotypeTest)
admin.site.register(Zygosity)


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

    def get_queryset(self, request):
        return (self.model.objects.
                filter(responsible_user=request.user).
                exclude(adverse_effects=''))

    def line_l(self, obj):
        # obj is the Subject instance, obj.line is the subject's Line instance.
        url = get_admin_url(obj.line)  # url to the Change line page
        return format_html('<a href="{url}">{line}</a>', line=obj.line or '-', url=url)
    line_l.short_description = 'line'


class CullMiceAdmin(SubjectAdmin):
    list_display = ['nickname', 'birth_date', 'death_date',
                    'ear_mark', 'line']
    ordering = ['-birth_date']
    list_filter = ['line']
    list_editable = ['death_date']


create_modeladmin(SubjectAdverseEffectsAdmin, model=Subject, name='Adverse effect')
create_modeladmin(CullMiceAdmin, model=Subject, name='Cull subject')
