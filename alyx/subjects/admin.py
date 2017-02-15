from django import forms
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import admin
from dal import autocomplete
from dal.forward import Const
from alyx.base import BaseAdmin, BaseInlineAdmin
from .models import *
from .views import _autoname_number
from actions.models import Surgery, Experiment


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


class ZygosityInline(BaseInlineAdmin):
    model = Zygosity
    extra = 2  # how many rows to show


class GenotypeTestInline(BaseInlineAdmin):
    model = GenotypeTest
    extra = 2  # how many rows to show


class SurgeryInline(BaseInlineAdmin):
    model = Surgery
    extra = 1


class ExperimentInline(BaseInlineAdmin):
    model = Experiment
    extra = 1


class SubjectAdmin(BaseAdmin):
    fieldsets = (
        ('SUBJECT', {'fields': ('nickname', 'sex', 'birth_date', 'age_days', 'responsible_user',
                                'death_date', 'ear_mark', 'notes')}),
        ('PROFILE', {'fields': ('species', 'strain', 'source', 'line')}),
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
               SurgeryInline, ExperimentInline]

    def weighing_plot(self, obj):
        url = reverse('weighing-plot', kwargs={'subject_id': obj.id})
        return format_html('<img src="{url}" />', url=url)


class SpeciesAdmin(BaseAdmin):

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['binomial']
        return self.readonly_fields

    list_display = ['binomial', 'display_name']
    readonly_fields = []


class SubjectLitterInline(BaseInlineAdmin):
    model = Subject
    extra = 1
    fields = ('age_weeks', 'sex', 'cage', 'litter', 'mother', 'father',
              'ear_mark', 'notes')
    readonly_fields = ('age_weeks', 'litter', 'mother', 'father',)
    show_change_link = True
    # TODO: genotype


class SubjectCageInline(BaseInlineAdmin):
    model = Subject
    extra = 1
    # fields = ('sex', 'ear_mark', 'notes')
    # TODO: genotype


class LineAdmin(BaseAdmin):
    fields = ['name', 'auto_name', 'gene_name', 'description']

    inlines = [SubjectLitterInline]


class LitterAdmin(BaseAdmin):
    list_display = ['descriptive_name', 'mother', 'father']
    fields = ['line', 'descriptive_name', 'birth_date', 'notes',
              'mother', 'father', 'cage']

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


class LitterInline(BaseInlineAdmin):
    model = Litter
    extra = 1
    show_change_link = True


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


admin.site.register(Subject, SubjectAdmin)
admin.site.register(Litter, LitterAdmin)
admin.site.register(Species, SpeciesAdmin)

admin.site.register(Line, LineAdmin)
admin.site.register(Allele)
admin.site.register(Sequence)
admin.site.register(Strain)
admin.site.register(Source)
admin.site.register(Cage, CageAdmin)
