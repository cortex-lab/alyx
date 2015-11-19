from django.contrib import admin
from .models import Subject

class SubjectDeadListFilter(admin.SimpleListFilter):
    title = 'dead'
    parameter_name = 'dead'

    def lookups(self, request, model_admin):
        return (
            ('y', 'Yes'),
            ('n', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'y':
            return queryset.exclude(death_date_time=None)
        if self.value() == 'n':
            return queryset.filter(death_date_time=None)

class SubjectAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'birth_date_time', 'responsible_user',
                    'strain', 'genotype', 'sex', 'dead']
    search_fields = ['nickname', 'responsible_user', 'dead']
    list_filter = [SubjectDeadListFilter]
    list_editable = []

admin.site.register(Subject, SubjectAdmin)