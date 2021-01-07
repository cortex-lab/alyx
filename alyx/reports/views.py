from django.http import HttpResponse

from django.template import loader

from experiments.models import TrajectoryEstimate, ProbeInsertion
from django.db.models import Count, Q
from misc.models import Lab


def current_datetime(request):
    template = loader.get_template('reports/simple.html')

    # BRAINWIDE INSERTIONS
    ins = ProbeInsertion.objects.filter(
        session__subject__projects__name='ibl_neuropixel_brainwide_01',
        session__qc__lt=50)

    # REP SITE
    traj = TrajectoryEstimate.objects.filter(
        provenance=10, x=-2243, y=-2000,
        probe_insertion__session__subject__projects__name='ibl_neuropixel_brainwide_01',
        probe_insertion__session__qc__lt=50)

    labs = Lab.objects.all()
    labs = labs.annotate(
        nrep=Count('subject__actions_sessions__probe_insertion__trajectory_estimate',
        filter=Q(subject__actions_sessions__probe_insertion__trajectory_estimate__in=traj)))
    # print(l.name, l.nrep)

    context = {
        "total": traj.count(),
        "labs": labs,
        "traj": traj,
        "ins": ins
    }

    return HttpResponse(template.render(context, request))
