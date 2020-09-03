from django.http import HttpResponse

from django.template import loader

from experiments.models import TrajectoryEstimate
from django.db.models import Count, Q
from misc.models import Lab


import datetime

def current_datetime(request):
    # now = datetime.datetime.now()
    template = loader.get_template('reports/simple.html')
    # context = {'now': now}

    te = TrajectoryEstimate.objects.filter(
        provenance=10, x=-2243, y=-2000,
        probe_insertion__session__subject__projects__name='ibl_neuropixel_brainwide_01')

    labs = Lab.objects.all()
    labs = labs.annotate(
        nrep=Count('subject__actions_sessions__probe_insertion__trajectory_estimate',
        filter=Q(subject__actions_sessions__probe_insertion__trajectory_estimate__in=te)))
    # print(l.name, l.nrep)

    context = {
        "total": te.count(),
        "labs": labs,
    }

    return HttpResponse(template.render(context, request))
