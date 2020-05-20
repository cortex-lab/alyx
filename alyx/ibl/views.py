import re

from django.http import HttpResponse
from django.template import loader
from django.shortcuts import render
from django.views.decorators.http import require_safe
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.contrib.admin import ModelAdmin
from actions.models import Session
from misc.models import LabMember, Lab
from data.models import Dataset
from subjects.models import Subject

from django.views.generic.list import ListView


def count_per_lab(labs, subjects):
    for lab in labs:
        lab_count = subjects.filter(lab__id=lab.id).count()
        yield {
                'institution': lab.institution,
                'count': lab_count,
                'pct': round((lab_count / subjects.count()) * 100),
                'total': subjects.count()
                }


@require_safe
def splash(request):

    if request.user.is_authenticated:
        username = request.user.first_name or request.user.username
    else:
        username = 'visitor'

    session_count = Session.objects.all().count()
    user_session_count = Session.objects.filter(type='Experiment', users__username__in=[username]).count()
    user_count = LabMember.objects.all().count()
    lab = Lab.objects.all()

    #line = ', '.join([re.sub('[!@#$"<>]', '', a['address']) for a in lab])
    datasets = Dataset.objects.all().exclude(file_records__exists=False)
    file_count = datasets.count()
    total_size = datasets.aggregate(Sum('file_size'))
    total_size = total_size['file_size__sum']
    live_subjects = Subject.objects.all().filter(
            death_date__isnull=True, 
            cull__isnull=True, 
            species__name='Mus musculus'
            )

    subject_count = live_subjects.count()
    n_ephys = Count('actions_sessions', filter=Q(actions_sessions__task_protocol__contains='ephys'))
    ephys_subject_count = live_subjects.annotate(
            num_ephys=n_ephys).filter(num_ephys__gt=0).count()

    lab_counts = count_per_lab(lab, live_subjects)
    print(lab_counts)

    n = 5
    last_n_sessions = (Session.objects.all()
            .annotate(water=Sum('wateradmin_session_related__water_administered'))
            .annotate(n_datasets=Count('data_dataset_session_related', distinct=True))
            .order_by('start_time').reverse())
    
    if request.user.is_authenticated:
        last_n_sessions = last_n_sessions.filter(users__username__in=request.user.username)

    with open('/etc/map_api_key.txt') as f:
        map_key = f.read().strip()

    template = loader.get_template('ibl/splash.html')
    context = {
            'name': username,
            'session_count': session_count,
            'user_session_count': user_session_count,
            'user_count': user_count,
            'lab_count': lab.count(),
            'file_count': file_count,
            'total_size': total_size,
            'subject_count': subject_count,
            'subject_lab_count': lab_counts,
            'ephys_subject_count': ephys_subject_count,
            'recent_sessions': last_n_sessions[:n],
            'site_header': 'Welcome to Alyx',
            'lab_list': lab,
            'map_key': map_key,
            'title': 'Alyx'
    }
    return HttpResponse(template.render(context, request))


class SubjectIncompleteListView(ListView):
    template_name = 'ibl/incomplete_subjects.html'
    paginate_by = 30
   
    def get_context_data(self, **kwargs):
        context = super(SubjectIncompleteListView, self).get_context_data(**kwargs)
        context['site_header'] = 'Alyx'
        context['title'] = 'Incomplete records'
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
        error_map = {
            'missing': missing
        }

        return missing
