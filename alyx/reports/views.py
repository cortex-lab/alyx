from django.http import HttpResponse, JsonResponse
from django_filters.views import FilterView
import django_filters
from django.template import loader
from django.views.generic.list import ListView
from experiments.models import TrajectoryEstimate, ProbeInsertion
from actions.models import Session
from django.db.models import Count, Q, F, Max, OuterRef, Exists
from misc.models import Lab
import numpy as np
from reports.qc_check import get_task_qc_colours
from reports import data_check


class InsertionOverview(ListView):
    template_name = 'reports/plots.html'

    def get_context_data(self, **kwargs):
        context = super(InsertionOverview, self).get_context_data(**kwargs)
        pid = self.kwargs.get('pid', None)
        probe = ProbeInsertion.objects.get(id=pid)
        dsets = probe.session.data_dataset_session_related

        context['probe'] = probe
        context['data'] = {}
        context['data']['passive'] = data_check.passive_data_status(dsets, probe)
        context['data']['behaviour'] = data_check.behaviour_data_status(dsets, probe)
        context['data']['trials'] = data_check.trial_data_status(dsets, probe)
        context['data']['wheel'] = data_check.wheel_data_status(dsets, probe)
        context['data']['raw_ephys'] = data_check.raw_ephys_data_status(dsets, probe)
        context['data']['dlc'] = data_check.dlc_data_status(dsets, probe)
        context['data']['video'] = data_check.video_data_status(dsets, probe)
        context['data']['spikesort'] = data_check.spikesort_data_status(dsets, probe)

        return context

    def get_queryset(self):
        lab = self.kwargs.get('lab', None)
        qs = Lab.objects.all().filter(name=lab)

        return qs


def plot_task_qc(request, pid):
    extended_qc = ProbeInsertion.objects.get(id=pid).session.extended_qc
    # TODO fix error when the extended qc is None
    task = {key: val for key, val in extended_qc.items() if '_task_' in key}
    col, bord = get_task_qc_colours(task)


    return JsonResponse({
        'title': f'Task QC: {extended_qc.get("task", "Not computed")}',
        'data': {
            'labels': list(task.keys()),
            'datasets': [{
                'label': 'QC Value',
                'backgroundColor': col,
                'borderColor': bord,
                'borderWidth': 3,
                'data': list(task.values()),
            }]
        },
    })

def plot_video_qc(request, pid):
    extended_qc = ProbeInsertion.objects.get(id=pid).session.extended_qc
    video = {key: val for key, val in extended_qc.items() if '_video_' in key}
    col, bord = get_task_qc_colours(video)

    return JsonResponse({
        'title': f'Task QC: {extended_qc["task"]}',
        'data': {
            'labels': list(video.keys()),
            'datasets': [{
                'label': 'QC Value',
                'backgroundColor': col,
                'borderColor': bord,
                'borderWidth': 2,
                'data': list(video.values()),
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


class InsertionTable(ListView):
    template_name = 'reports/table.html'
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super(InsertionTable, self).get_context_data(**kwargs)
        context['chosen_lab'] = self.lab
        context['data_status'] = data_check.get_data_status_qs(context['object_list'])
        context['labs'] = Lab.objects.all().exclude(name=self.lab)

        return context

    def get_queryset(self):

        self.lab = self.request.GET.get('lab', None)
        qs = ProbeInsertion.objects.all().filter(
            session__project__name='ibl_neuropixel_brainwide_01')
        if self.lab:
            qs = qs.filter(session__lab__name=self.lab)

        qs = qs.annotate(task=F('session__extended_qc__task'),
                         video_left=F('session__extended_qc__videoLeft'),
                         video_right=F('session__extended_qc__videoRight'),
                         video_body=F('session__extended_qc__videoBody'),
                         behavior=F('session__extended_qc__behavior'),
                         insertion_qc=F('json__qc'))
        qs = qs.annotate(planned=Exists(
            TrajectoryEstimate.objects.filter(probe_insertion=OuterRef('pk'), provenance=10)))
        qs = qs.annotate(micro=Exists(
            TrajectoryEstimate.objects.filter(probe_insertion=OuterRef('pk'), provenance=30)))
        qs = qs.annotate(histology=Exists(
            TrajectoryEstimate.objects.filter(probe_insertion=OuterRef('pk'), provenance=50,
                                              x__isnull=False)))
        #qs = qs.annotate(resolved=Exists(
        #   TrajectoryEstimate.objects.filter(probe_insertion=OuterRef('pk'), provenance=70)))
        qs = qs.annotate(resolved=F('json__extended_qc__alignment_resolved'))

        return qs.order_by('-session__start_time')


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