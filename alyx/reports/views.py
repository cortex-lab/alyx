from django.http import HttpResponse, JsonResponse

from django.template import loader
from django.views.generic.list import ListView
from experiments.models import TrajectoryEstimate, ProbeInsertion
from actions.models import Session
from django.db.models import Count, Q, F, Max
from misc.models import Lab
import numpy as np


def session_option(request):
    grouped_purchases = Session.objects.filter(lab__name='hoferlab').order_by('-start_time')
    options = [purchase.id for purchase in grouped_purchases]

    return JsonResponse({
        'options': options,
    })

def plot_task_qc(request, eid):
    sess = Session.objects.get(id=eid)
    task = {key: val for key, val in sess.extended_qc.items() if '_task' in key}

    return JsonResponse({
        'title': f'Sales in {eid}',
        'data': {
            'labels': list(task.keys()),
            'datasets': [{
                'label': 'Amount ($)',
                'backgroundColor': "#79AEC8",
                'borderColor': "#417690",
                'data': list(task.values()),
            }]
        },
    })



class AlertsLabView(ListView):
    template_name = 'reports/plots.html'

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

        ins = ProbeInsertion.objects.filter(session__lab__name=lab_name).\
            order_by('-session__start_time')

        traj_plan = TrajectoryEstimate.objects.filter(
            probe_insertion__session__lab__name=lab_name, provenance=10)
        traj_micro = TrajectoryEstimate.objects.filter(
            probe_insertion__session__lab__name=lab_name, provenance=30)
        traj_hist = TrajectoryEstimate.objects.filter(
            probe_insertion__session__lab__name=lab_name, provenance=50)
        traj_ephys = TrajectoryEstimate.objects.filter(
            probe_insertion__session__lab__name=lab_name, provenance=70)

        context['no_ins_plan'] = ins.exclude(pk__in=traj_plan.values_list('probe_insertion',
                                                                          flat=True))
        context['no_ins_micro'] = ins.exclude(pk__in=traj_micro.values_list('probe_insertion',
                                                                            flat=True))
        context['no_ins_hist'] = ins.exclude(pk__in=traj_hist.values_list('probe_insertion',
                                                                          flat=True))
        context['no_ins_ephys'] = ins.filter(pk__in=traj_hist.values_list('probe_insertion',
                                                                          flat=True)).\
            exclude(pk__in=traj_ephys.values_list('probe_insertion', flat=True))

        return context

    def get_queryset(self):
        lab = self.kwargs.get('lab', None)
        qs = Lab.objects.all().filter(name=lab)

        return qs

class AlertsInsertionView(ListView):
    template_name = 'reports/insertions.html'

    def get_context_data(self, **kwargs):
        lab_name = self.kwargs.get('lab', None)
        labs_all = Lab.objects.all().order_by('name')
        context = super(AlertsInsertionView, self).get_context_data(**kwargs)
        labs = Lab.objects.all().filter(name=lab_name)

        ins = ProbeInsertion.objects.filter(session__lab__name=lab_name)
        # annotate by if they are first pass map


        traj_plan = TrajectoryEstimate.objects.filter(
            probe_insertion__session__lab__name=lab_name, provenance=10)
        traj_micro = TrajectoryEstimate.objects.filter(
            probe_insertion__session__lab__name=lab_name, provenance=30)
        traj_hist = TrajectoryEstimate.objects.filter(
            probe_insertion__session__lab__name=lab_name, provenance=50)
        traj_ephys = TrajectoryEstimate.objects.filter(
            probe_insertion__session__lab__name=lab_name, provenance=70)

        context['no_ins_plan'] = ins.exclude(pk__in=traj_plan.values_list('probe_insertion',
                                                                          flat=True))
        context['no_ins_micro'] = ins.exclude(pk__in=traj_micro.values_list('probe_insertion',
                                                                            flat=True))
        context['no_ins_hist'] = ins.exclude(pk__in=traj_hist.values_list('probe_insertion',
                                                                          flat=True))
        context['no_ins_ephys'] = ins.filter(pk__in=traj_hist.values_list('probe_insertion',
                                                                          flat=True)).\
            exclude(pk__in=traj_ephys.values_list('probe_insertion', flat=True))


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
