from django import forms
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import admin
from dal import autocomplete
from alyx.base import BaseAdmin, BaseInlineAdmin
from .models import *
from .views import _autoname_number
from actions.models import Surgery, Experiment


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
        ('SUBJECT', {'fields': ('nickname', 'sex', 'birth_date', 'age_days', 'responsible_user',
                                'death_date', 'ear_mark', 'notes', 'json')}),
        ('PROFILE', {'fields': ('species', 'strain', 'source', 'line',)}),
        ('LITTER', {'fields': ('cage', 'litter',)}),
        ('WEIGHINGS/WATER', {'fields': ('water_restriction_date',
                                        'reference_weighing',
                                        'current_weighing',
                                        'implant_weight',
                                        'water_requirement_total',
                                        'water_requirement_remaining',
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
                       'reference_weighing',
                       'current_weighing',
                       'water_requirement_total',
                       'water_requirement_remaining',
                       'weighing_plot',
                       )
    list_filter = [SubjectAliveListFilter, ResponsibleUserListFilter]
    inlines = [ZygosityInline, GenotypeTestInline,
               SurgeryInline, ExperimentInline, OtherActionInline]

    def weighing_plot(self, obj):
        url = reverse('weighing-plot', kwargs={'subject_id': obj.id})
        return format_html('<img src="{url}" />', url=url)


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


class SubjectCageInline(BaseInlineAdmin):
    model = Subject
    extra = 1
    # fields = ('sex', 'ear_mark', 'notes')
    # TODO: genotype


class CageAdminForm(forms.ModelForm):

    cage_label = forms.CharField(
        widget=autocomplete.Select2(url='cage-label-autocomplete',
                                    forward=['line'],
                                    ),
        required=True,
    )

    class Meta:
        fields = '__all__'
        model = Cage


class CageAdmin(BaseAdmin):
    form = CageAdminForm

    fields = ('line', 'cage_label', 'type', 'location')
    inlines = [SubjectCageInline, LitterInline]

    def get_form(self, request, obj=None, **kwargs):
        # just save obj reference for future processing in Inline
        request._obj_ = obj
        return super(CageAdmin, self).get_form(request, obj, **kwargs)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        # Set the line of all inline litters.
        for instance in instances:
            if isinstance(instance, Litter):
                instance.line = formset.instance.line
                instance.save()
        formset.save_m2m()


# Litter
# ------------------------------------------------------------------------------------------------

class SubjectLitterInline(BaseInlineAdmin):
    model = Subject
    extra = 1
    fields = ('age_weeks', 'sex', 'cage', 'litter', 'mother', 'father',
              'ear_mark', 'notes')
    readonly_fields = ('age_weeks', 'litter', 'mother', 'father',)
    show_change_link = True


class LitterAdmin(BaseAdmin):
    list_display = ['descriptive_name', 'mother', 'father', 'birth_date']
    fields = ['line', 'descriptive_name',
              'mother', 'father', 'birth_date',
              'notes', 'cage']

    inlines = [SubjectLitterInline]

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
            prefix = getattr(subj.line, 'name', 'UNKNOWN') + '_'
            i = _autoname_number(Subject, 'nickname', prefix)
            subj.nickname = '%s%04d' % (prefix, i)
            subj.save()
        formset.save_m2m()


# Line
# ------------------------------------------------------------------------------------------------

class SequencesInline(BaseInlineAdmin):
    model = Line.sequences.through

    fields = ['sequence']


class LineAdmin(BaseAdmin):
    fields = ['name', 'auto_name', 'gene_name', 'strain', 'species', 'description']

    inlines = [SequencesInline, SubjectLitterInline]

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        # Delete objects marked to delete.
        for obj in formset.deleted_objects:
            obj.delete()
        line = formset.instance
        to_copy = 'species,strain'.split(',')
        for instance in instances:
            subj = instance
            if isinstance(subj, Subject):
                # Copy some fields from the line to the subject.
                for field in to_copy:
                    value = getattr(line, field, None)
                    if value:
                        setattr(subj, field, value)
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
