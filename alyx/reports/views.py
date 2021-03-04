from django.http import HttpResponse

from django.template import loader
from django.views.generic.list import ListView
from experiments.models import TrajectoryEstimate, ProbeInsertion
from django.db.models import Count, Q, F, Max
from misc.models import Lab
import numpy as np


class AlertsLabView(ListView):
    template_name = 'reports/alerts2.html'

    def get_context_data(self, **kwargs):
        lab_name = self.kwargs.get('lab', None)
        labs_all = Lab.objects.all().order_by('name')
        context = super(AlertsLabView, self).get_context_data(**kwargs)
        labs = Lab.objects.all().filter(name=lab_name)
        ntraining = Count("session", filter=Q(session__procedures__name='Behavior training/tasks'))
        nephys = Count("session", filter=Q(session__procedures__name__icontains='ephys'))
        lt_training = Max("session__start_time",
                          filter=Q(session__procedures__name='Behavior training/tasks'))
        lt_ephys = Max("session__start_time",
                       filter=Q(session__procedures__name__icontains='ephys'))
        labs = labs.annotate(ntraining=ntraining, nephys=nephys, latest_training=lt_training,
                             latest_ephys=lt_ephys)

        # Annotate with latest ephys session

        space = np.array(labs.values_list(
            'json__raid_available', flat=True), dtype=np.float)
        context['space_left'] = np.round(space / 1000, decimals=1)
        context['labs'] = labs
        context['labs_all'] = labs_all

        return context

    def get_queryset(self):
        lab = self.kwargs.get('lab', None)
        qs = Lab.objects.all().filter(name=lab)

        return qs


def basepage(request):
    template = loader.get_template('reports/base.html')
    context = dict()
    labs = Lab.objects.all().order_by('name')
    context['labs_all'] = labs

    return HttpResponse(template.render(context, request))

def alerts(request):
    template = loader.get_template('reports/alerts.html')
    context = dict()
    labs = Lab.objects.all().order_by('name')
    labs = labs.annotate(
        ntraining=Count(
            "session",
            filter=Q(session__procedures__name='Behavior training/tasks')
        )
    )
    labs = labs.annotate(nephys=Count("session",
            filter=Q(session__procedures__name__icontains='ephys')))

    labs = labs.annotate(
        latest_training=Max(
            "session__start_time",
            filter=Q(session__procedures__name='Behavior training/tasks')
        )
    )

    labs = labs.annotate(
        latest_ephys=Max(
            "session__start_time",
            filter=Q(session__procedures__name__icontains='ephys')
        )
    )

    # Annotate with latest ephys session

    space = np.array(labs.values_list(
            'json__raid_available', flat=True), dtype=np.float)
    context['space_left'] = np.round(space / 1000, decimals=1)
    context['labs'] = labs

    #context = {'labs': labs}
    return HttpResponse(template.render(context, request))


def current_datetime(request):
    template = loader.get_template('reports/simple.html')

    # BRAINWIDE INSERTIONS
    pins = ProbeInsertion.objects.filter(
        session__subject__projects__name='ibl_neuropixel_brainwide_01',
        session__qc__lt=50)
    cam_notes = []
    for pi in pins:
        note = pi.session.notes.filter(text__icontains='Camera images').first()
        if note is None:
            url = 'https://upload.wikimedia.org/wikipedia/commons/4/45/Carré_rouge.svg'
        else:
            url = note.image.url
        cam_notes.append(url)

    # # Notes
    # notes_camera = Note.objects.filter(text__icontains='Camera images')

    # REP SITE
    traj = TrajectoryEstimate.objects.filter(
        provenance=10, x=-2243, y=-2000,
        probe_insertion__session__subject__projects__name='ibl_neuropixel_brainwide_01',
        probe_insertion__session__qc__lt=50)

    labs = Lab.objects.all()
    labs = labs.annotate(
        nrep=Count(
            'subject__actions_sessions__probe_insertion__trajectory_estimate',
            filter=Q(subject__actions_sessions__probe_insertion__trajectory_estimate__in=traj)
        )
    )
    # print(l.name, l.nrep)

    context = {
        "total": traj.count(),
        "labs": labs,
        "traj": traj,
        "pins": pins,
        "zip_var": zip(pins, cam_notes)
    }

    return HttpResponse(template.render(context, request))

# Q1 : how to link item to insertion when they relate to session
# Q2 : how to put new fields in (e.g. result of test for datasets)
