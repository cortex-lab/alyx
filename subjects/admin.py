from django.contrib import admin
from .models import Subject, Species

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
            return queryset.filter(death_date_time=None)
        if self.value() == 'n':
            return queryset.exclude(death_date_time=None)

class SubjectAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'birth_date_time', 'responsible_user',
                    'strain', 'genotype', 'sex', 'alive']
    search_fields = ['nickname', 'responsible_user', 'alive']
    list_filter = [SubjectAliveListFilter]

class SpeciesAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['binomial']
        return self.readonly_fields

    list_display = ['binomial', 'display_name']
    readonly_fields = []

admin.site.register(Subject, SubjectAdmin)
admin.site.register(Species, SpeciesAdmin)