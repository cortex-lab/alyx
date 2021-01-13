from django.http import HttpResponse

from django.template import loader

from experiments.models import TrajectoryEstimate, ProbeInsertion
from misc.models import Note
from django.db.models import Count, Q
from misc.models import Lab


def current_datetime(request):
    template = loader.get_template('reports/simple.html')

    # BRAINWIDE INSERTIONS
    pins = ProbeInsertion.objects.filter(
        session__subject__projects__name='ibl_neuropixel_brainwide_01',
        session__qc__lt=50)
    cam_note = []
    for pi in pins:
        note = pi.session.notes.filter(text__icontains='Camera images').first()
        if note is None:
            url = 'https://upload.wikimedia.org/wikipedia/commons/4/45/Carré_rouge.svg'
        else:
            url = note.image.url
        cam_note.append(url)

    # # Notes
    # notes_camera = Note.objects.filter(text__icontains='Camera images')

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
        "pins": pins,
        "notes_camera": cam_note,
        "zip_var": zip(pins, cam_note)
    }

    return HttpResponse(template.render(context, request))

# Q1 : how to link item to insertion when they relate to session
# Q2 : how to put new fields in (e.g. result of test for datasets)
