from django.db.models import Sum, Count, Q
from django.contrib.admin import ModelAdmin
from actions.models import Session
from misc.models import LabMember, Lab
from data.models import Dataset
from subjects.models import Subject

from django.views.generic.list import ListView


class SubjectIncompleteListView(ListView):
    template_name = 'incomplete/incomplete_subjects.html'
    paginate_by = 30
   
    def get_context_data(self, **kwargs):
        context = super(SubjectIncompleteListView, self).get_context_data(**kwargs)
        context['site_header'] = 'Alyx'
        context['title'] = 'Incomplete records'
        context['error_map'] = self.error_map
        return context

    def get_queryset(self):
        user = self.request.user.username
        #subject = Subject.objects.filter(responsible_user__username__in=user)
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

        # TODO Add more sets and combine based on filter
        self.error_map = {
            'missing': missing
        }

        return missing
