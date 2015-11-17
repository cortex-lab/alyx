from django.contrib import admin
from .models import Subject

class SubjectAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'responsible_user',
                    'strain', 'genotype', 'sex', 'dead']
    search_fields = ['nickname', 'responsible_user', 'dead']
    list_filter = ['dead']
    list_editable = []