from django import forms
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import admin
from alyx.base import BaseAdmin, BaseInlineAdmin
from .models import *
from .views import _autoname, _autoname_number
from actions.models import Surgery, Experiment, OtherAction


# Filters
# ------------------------------------------------------------------------------------------------

class ResponsibleUserListFilter(admin.SimpleListFilter):
    title = 'responsible user'
    parameter_name = 'responsible_user'

    def lookups(self, request, model_admin):
        return (
            ('m', 'Me'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'm':
            return queryset.filter(responsible_user=request.user)


class SubjectAliveListFilter(admin.SimpleListFilter):
    title = 'alive'
    parameter_name = 'alive'

    def lookups(self, request, model_admin):
        return (
            ('y', 'Yes'),
            ('n', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'y':
            return queryset.filter(death_date=None)
        if self.value() == 'n':
            return queryset.exclude(death_date=None)


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
    fields = ['brain_location', 'procedures', 'narrative', 'date_time',
              'users', 'location']


class ExperimentInline(BaseInlineAdmin):
    model = Experiment
    extra = 1
    fields = ['procedures', 'narrative', 'date_time',
              'users', 'location']


class OtherActionInline(BaseInlineAdmin):
    model = OtherAction
    extra = 1
    fields = ['procedures', 'narrative', 'date_time',
              'users', 'location']


class SubjectAdmin(BaseAdmin):
    fieldsets = (
        ('SUBJECT', {'fields': ('nickname', 'sex', 'birth_date', 'age_days', 'cage',
                                'responsible_user',
                                'death_date', 'ear_mark', 'notes', 'json')}),
        ('PROFILE', {'fields': ('species', 'strain', 'source', 'line', 'litter')}),
        ('WEIGHINGS/WATER', {'fields': ('water_restriction_date',
                                        'reference_weighing_f',
                                        'current_weighing_f',
                                        'implant_weight',
                                        'water_requirement_total_f',
                                        'water_requirement_remaining_f',
                                        'weighing_plot',
                                        )}),
    )

    list_display = ['nickname', 'birth_date', 'responsible_user',
                    'cage', 'mother', 'father',
                    'sex', 'alive']
    search_fields = ['nickname',
                     'responsible_user__first_name',
                     'responsible_user__last_name',
                     'responsible_user__username']
    readonly_fields = ('age_days',
                       'water_restriction_date',
                       'reference_weighing_f',
                       'current_weighing_f',
                       'water_requirement_total_f',
                       'water_requirement_remaining_f',
                       'weighing_plot',
                       )
    list_filter = [SubjectAliveListFilter, ResponsibleUserListFilter]
    inlines = [ZygosityInline, GenotypeTestInline,
               SurgeryInline, ExperimentInline, OtherActionInline]

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
    fields = ('nickname', 'age_weeks', 'sex', 'cage', 'litter', 'mother', 'father',
              'sequence0', 'result0',
              'sequence1', 'result1',
              'sequence2', 'result2',
              'ear_mark', 'notes')
    readonly_fields = ('age_weeks', 'litter', 'mother', 'father',
                       'sequence0', 'sequence1', 'sequence2',
                       )
    show_change_link = True
    form = SubjectInlineForm

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # Filter cages by cages that are part of that line.
        field = super(SubjectInline, self).formfield_for_foreignkey(db_field,
                                                                    request, **kwargs)

        if db_field.name == 'cage':
            if isinstance(request._obj_, Line):
                field.queryset = field.queryset.filter(line=request._obj_)
            else:
                field.queryset = field.queryset.none()

        return field

    def _get_sequence(self, obj, i):
        if obj and obj.line:
            sequences = obj.line.sequences.all()
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

    fields = ('line', 'cage_label', 'type', 'location')
    inlines = [SubjectInline, LitterInline]

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        return super(CageAdmin, self).get_form(request, obj, **kwargs)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        if formset.instance.cage_label in (None, '-'):
            autoname = _autoname(Cage,
                                 formset.instance.line.auto_name,
                                 'cage_label',
                                 interfix='C_')
            formset.instance.cage_label = autoname
            formset.instance.save()
        # Set the line of all inline litters.
        for instance in instances:
            if isinstance(instance, Litter):
                instance.line = formset.instance.line
                if instance.descriptive_name in (None, '-'):
                    autoname = _autoname(Litter,
                                         formset.instance.line.auto_name,
                                         'descriptive_name',
                                         interfix='L_')
                    instance.descriptive_name = autoname
            elif isinstance(instance, Subject):
                if instance.nickname in (None, '-'):
                    autoname = _autoname(Subject,
                                         formset.instance.line.auto_name,
                                         'nickname',
                                         interfix='')
                    instance.nickname = autoname
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

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        litter = formset.instance
        mother = litter.mother
        to_copy = 'cage,species,strain,line,source,responsible_user'.split(',')
        for instance in instances:
            subj = instance
            subj.birth_date = litter.birth_date
            # Copy some fields from the mother to the subject.
            for field in to_copy:
                setattr(subj, field, getattr(mother, field))
            # Autofill nickname.
            if subj.nickname in (None, '-'):
                autoname = _autoname(Subject,
                                     litter.line.auto_name,
                                     'nickname',
                                     interfix='')
                subj.nickname = autoname
            subj.save()
        formset.save_m2m()


# Line
# ------------------------------------------------------------------------------------------------

class SubjectRequestInline(BaseInlineAdmin):
    model = SubjectRequest
    extra = 1
    fields = ['count', 'due_date', 'status', 'notes']


class SequencesInline(BaseInlineAdmin):
    model = Line.sequences.through
    extra = 1
    fields = ['sequence']


class LineAdmin(BaseAdmin):
    fields = ['name', 'auto_name', 'target_phenotype', 'strain', 'species', 'description']

    inlines = [SubjectRequestInline, SubjectInline, SequencesInline]

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
            subj = instance
            if isinstance(subj, Subject):
                # Copy some fields from the line to the subject.
                for field in ('species', 'strain'):
                    value = getattr(line, field, None)
                    if value:
                        setattr(subj, field, value)
                if subj.nickname in (None, '-'):
                    autoname = _autoname(Subject,
                                         line.auto_name,
                                         'nickname',
                                         interfix='')
                    subj.nickname = autoname
            elif isinstance(subj, SubjectRequest):
                # Copy some fields from the line to the subject.
                subj.user = request.user
            subj.save()
        formset.save_m2m()


# Other
# ------------------------------------------------------------------------------------------------

class SubjectRequestAdmin(BaseAdmin):
    fields = ['line', 'count', 'date_time', 'due_date', 'status', 'notes', 'user']


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
