from django.contrib import admin
from .models import *

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
            return queryset.filter(death_date_time=None)
        if self.value() == 'n':
            return queryset.exclude(death_date_time=None)

class ZygosityInline(admin.TabularInline):
    model = Zygosity
    extra = 2 # how many rows to show

class SubjectAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'birth_date', 'responsible_user',
                    'strain', 'sex', 'alive']
    search_fields = ['nickname', 'responsible_user__first_name',
                     'responsible_user__last_name', 'responsible_user__username',
                     'strain']
    list_filter = [SubjectAliveListFilter, ResponsibleUserListFilter]
    inlines = [ZygosityInline,]


class SpeciesAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['binomial']
        return self.readonly_fields

    list_display = ['binomial', 'display_name']
    readonly_fields = []


class LitterAdmin(admin.ModelAdmin):
    list_display = ['mother', 'father']

admin.site.register(Subject, SubjectAdmin)
admin.site.register(Litter, LitterAdmin)
admin.site.register(Species, SpeciesAdmin)

admin.site.register(Allele)
admin.site.register(Strain)
admin.site.register(Source)
admin.site.register(Cage)
