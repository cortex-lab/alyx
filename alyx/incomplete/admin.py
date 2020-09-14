from django.contrib import admin
from django.db.models import Q
from .models import Incomplete
from alyx.base import BaseAdmin, DefaultListFilter
from subjects.models import Subject
from pprint import pprint

# Filters | NB: Failed to import from subjects
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


class LabMemberListFilter(DefaultListFilter):
    title = 'lab location'
    parameter_name = 'lab_location'

    def lookups(self, request, model_admin):
        return (
            (None, 'All'),
            ('mine', 'Mine')
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


# Admin
# --------------------------------------------------------------------------
# https://docs.djangoproject.com/en/3.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.get_form
# https://docs.djangoproject.com/en/3.0/ref/forms/models/#django.forms.models.modelform_factory
# https://stackoverflow.com/questions/7562573/how-do-i-get-django-forms-to-show-the-html-required-attribute/37738828#37738828
# https://stackoverflow.com/questions/10838415/access-form-field-attributes-in-templated-django
class IncompleteAdmin(BaseAdmin):
    list_display = ['nickname', 'birth_date', 'line', 'strain', 'sex', 'cage', 'species', 'cull_reason_']
    list_editable = ['birth_date', 'line', 'strain', 'sex', 'cage', 'species']
    #autocomplete_fields = ['cage']
    list_per_page = 5
    list_filter = [ResponsibleUserListFilter, SubjectAliveListFilter, 'lab']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print('hi')
        print( self.fields)

    def get_form(self, request, obj=None, **kwargs):
        """Attempted to add 'required' attribute to the input dialogs in order to
        style them in CSS (red background for empty / unassigned fields) however 
        I'm unable to find the widgets
        """
        form = super(BaseAdmin, self).get_form(request, obj=None, **kwargs)
        css = {'style': 'outline:none;border-color:#9ecaed;box-shadow: 0 0 10px #9ecaed'}
        form.fields['cage'].widget.attrs.update({'style': 'background-color:red;'})
        return form

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def cull_reason_(self, obj):
        if hasattr(obj, 'cull'):
            return obj.cull.cull_reason
    cull_reason_.short_description = 'cull reason'

    def get_queryset(self, request):
        missing = (Subject.objects.filter(
            Q(lab__isnull=True) |
            Q(sex__in='U') | 
            Q(birth_date__isnull=True) |
            Q(cage__isnull=True) |
            Q(strain__isnull=True) |
            Q(line__isnull=True) |
            Q(litter__isnull=True) |
            Q(species__isnull=True) |
            (Q(death_date__isnull=False) | Q(cull__isnull=False)) &
             Q(cull__cull_reason__isnull=True)))
        return missing

admin.site.register(Incomplete, IncompleteAdmin)
