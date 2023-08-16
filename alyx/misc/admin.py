from pytz import all_timezones

from django import forms
from django.db import models
from django.db.models import Q
from django.contrib import admin
from django.contrib.admin.widgets import AdminFileWidget
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.postgres.fields import JSONField
from django.utils.html import format_html, format_html_join

from misc.models import Note, Lab, LabMembership, LabLocation, CageType, \
    Enrichment, Food, Housing, HousingSubject
from alyx.base import BaseAdmin, DefaultListFilter, get_admin_url


class LabForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(LabForm, self).__init__(*args, **kwargs)
        # if user has read-only permissions only fields is empty
        if not self.is_bound:
            return
        self.fields['reference_weight_pct'].help_text =\
            'Threshold ratio triggers a warning using the Reference Weight method (0-1)'
        self.fields['reference_weight_pct'].label = 'Reference Weight Ratio'
        self.fields['zscore_weight_pct'].help_text =\
            'Threshold ratio triggers a warning is raised using the Z-Score method (0-1)'
        self.fields['zscore_weight_pct'].label = 'Z-score Weight Ratio'

    def clean_reference_weight_pct(self):
        ref = self.cleaned_data['reference_weight_pct']
        ref = max(ref, 0)
        if ref > 1:
            ref = ref / 100
        return ref

    def clean_zscore_weight_pct(self):
        ref = self.cleaned_data['zscore_weight_pct']
        ref = max(ref, 0)
        if ref > 1:
            ref = ref / 100
        return ref

    def clean_timezone(self):
        ref = self.cleaned_data['timezone']
        if ref not in all_timezones:
            raise forms.ValidationError(
                ("Time Zone is incorrect here is the list (column TZ Database Name):  "
                 "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"))
        return ref


class LabAdmin(BaseAdmin):
    form = LabForm
    generics = ['name', 'institution', 'address', 'timezone',
                'reference_weight_pct', 'zscore_weight_pct']
    list_display = ['name', 'institution', 'address', 'timezone', 'local', 'server',
                    'reference_weight_pct', 'zscore_weight_pct']
    list_select_related = ['cage_type', 'enrichment', 'food']
    fields = generics + list_select_related + ['cage_cleaning_frequency_days', 'light_cycle',
                                               'repositories']

    def local(self, obj):
        return ','.join([p.name for p in obj.repositories.filter(globus_is_personal=True)])

    def server(self, obj):
        return ','.join([p.name for p in obj.repositories.filter(globus_is_personal=False)])


class LabMembershipAdmin(BaseAdmin):
    fields = ['user', 'lab', 'role', 'start_date', 'end_date']
    list_display = fields


class LabLocationAdmin(BaseAdmin):
    fields = ['name', 'lab']
    list_display = fields
    search_fields = ('lab__name', 'name',)
    ordering = ('lab__name', 'name',)


class AdminImageWidget(AdminFileWidget):
    def render(self, name, value, attrs=None, renderer=None):
        output = []
        if value and getattr(value, "url", None):
            image_url = value.url
            file_name = str(value)
            output.append(('<a href="%s" target="_blank">'
                           '<img src="%s" width="400" alt="%s" /></a><br>') %
                          (image_url, image_url, file_name))
        output.append(super(AdminFileWidget, self).render(name, value, attrs, renderer))
        return ''.join(output)


class ImageWidgetAdmin(BaseAdmin):
    image_fields = []

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in self.image_fields:
            request = kwargs.pop("request", None)  # noqa
            kwargs['widget'] = AdminImageWidget
            return db_field.formfield(**kwargs)
        return super(ImageWidgetAdmin, self).formfield_for_dbfield(db_field, **kwargs)


class NoteAdmin(ImageWidgetAdmin):
    list_display = ['user', 'date_time', 'content_object', 'text', 'image']
    list_display_links = ['date_time']
    image_fields = ['image']
    fields = ['user', 'date_time', 'text', 'image', 'content_type', 'object_id']
    ordering = ('-date_time',)
    search_fields = ['text']


class NoteInline(GenericTabularInline):
    model = Note
    extra = 1
    fields = ('user', 'date_time', 'text', 'image')
    image_fields = ('image',)
    ordering = ('-date_time',)

    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(
                           attrs={'rows': 3,
                                  'cols': 30})},
        JSONField: {'widget': forms.Textarea(
                    attrs={'rows': 3,
                           'cols': 30})},
        models.CharField: {'widget': forms.TextInput(attrs={'size': 16})},
    }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Logged-in user by default.
        if db_field.name == 'user':
            kwargs['initial'] = request.user
        return super(NoteInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in self.image_fields:
            request = kwargs.pop("request", None)  # noqa
            kwargs['widget'] = AdminImageWidget
            return db_field.formfield(**kwargs)
        return super(NoteInline, self).formfield_for_dbfield(db_field, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False


class CageTypeAdmin(BaseAdmin):
    fields = ('name', 'description',)
    list_display = fields
    search_fields = ('name',)


class EnrichmentAdmin(BaseAdmin):
    fields = ('name', 'description',)
    list_display = fields
    search_fields = ('name',)


class FoodAdmin(BaseAdmin):
    fields = ('name', 'description',)
    list_display = fields
    search_fields = ('name',)


class HousingSubjectAdminInline(admin.TabularInline):
    model = HousingSubject
    extra = 1
    fields = ('subject', 'start_datetime', 'end_datetime')

    def get_queryset(self, request):
        qs = super(HousingSubjectAdminInline, self).get_queryset(request)
        return qs.filter(subject__cull__isnull=True)


class HousingAdminForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.Meta.formfield_callback.keywords['request']
        self.user = request.user
        lab = self.user.lab_id()
        if lab:
            self.fields['cage_type'].initial = lab[0].cage_type
            self.fields['enrichment'].initial = lab[0].enrichment
            self.fields['light_cycle'].initial = lab[0].light_cycle
            self.fields['food'].initial = lab[0].food
            self.fields['cage_cleaning_frequency_days'].initial =\
                lab[0].cage_cleaning_frequency_days

    class Meta():
        model = Housing
        fields = ['cage_type', 'cage_name',
                  'enrichment', 'light_cycle',
                  'food', 'cage_cleaning_frequency_days']


class HousingIsCurrentFilter(DefaultListFilter):
    title = 'Housing Current'
    parameter_name = 'Housing Current'

    def lookups(self, request, model_admin):
        return (
            (None, 'Current'),
            ('All', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.exclude(nsubs=0)


class HousingAdmin(BaseAdmin):

    inlines = [HousingSubjectAdminInline]
    form = HousingAdminForm

    fields = ['subjects_l',
              ('cage_type', 'cage_name'),
              ('enrichment', 'light_cycle',),
              ('food', 'cage_cleaning_frequency_days')]
    search_fields = ('housing_subjects__subject__nickname', 'housing_subjects__subject__lab__name')
    list_display = ('cage_l', 'subjects_l', 'subjects_old', 'start',
                    'end', 'subjects_count', 'lab',)
    readonly_fields = ('subjects_l',)
    list_filter = (HousingIsCurrentFilter,)

    def get_queryset(self, request):
        qs = Housing.objects.annotate(
            nsubs=models.Count('housing_subjects',
                               filter=Q(housing_subjects__end_datetime__isnull=True),
                               distinct=True))
        qs = qs.annotate(start_datetime=models.Min('housing_subjects__start_datetime'))
        qs = qs.annotate(end_datetime=models.Case(models.When(
            nsubs=0, then=models.Max('housing_subjects__end_datetime')),
            output_field=models.DateTimeField(),))
        return qs

    def start(self, obj):
        return obj.start_datetime

    def end(self, obj):
        return obj.end_datetime

    def subjects_count(self, obj):
        return obj.nsubs
    subjects_count.short_description = '# active'

    def cage_l(self, obj):
        return format_html('<a href="{url}">{hou}</a>', url=get_admin_url(obj), hou=obj.cage_name)
    cage_l.short_description = 'cage'

    def subjects_l(self, obj):
        out = format_html_join(', ', '<a href="{}">{}</a>',
                               ((get_admin_url(sub), sub) for sub in obj.subjects_current()))
        return format_html(out)
    subjects_l.short_description = 'subjects'

    def subjects_old(self, obj):
        subs = obj.subjects.exclude(pk__in=obj.subjects_current().values_list('pk', flat=True))
        out = format_html_join(', ', '<a href="{}">{}</a>',
                               ((get_admin_url(sub), sub) for sub in subs))
        return format_html(out)
    subjects_old.short_description = 'old subjects'


admin.site.register(Housing, HousingAdmin)
admin.site.register(Lab, LabAdmin)
admin.site.register(LabMembership, LabMembershipAdmin)
admin.site.register(LabLocation, LabLocationAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(CageType, CageTypeAdmin)
admin.site.register(Enrichment, EnrichmentAdmin)
admin.site.register(Food, FoodAdmin)
