'''
Alyx reports page on probe insertion status

Gaelle, Olivier, Cyrille
Jan 2021
'''
from django.http import HttpResponse
from django.template import loader

from experiments.models import TrajectoryEstimate, ProbeInsertion
from misc.models import Lab, Note
from django.db.models import Count, Q, Subquery, OuterRef
from misc.models import Lab

from alyx.settings import MEDIA_URL


def current_datetime(request):
    template = loader.get_template('reports/simple.html')

    # BRAINWIDE INSERTIONS
    probes = ProbeInsertion.objects.filter(
        session__subject__projects__name='ibl_neuropixel_brainwide_01',
        session__qc__lt=50)

    cam_notes = Note.objects.filter(text__icontains='Camera images', object_id=OuterRef('session'))
    raster_notes = Note.objects.filter(text__icontains='Drift', object_id=OuterRef('pk'))
    probes = probes.annotate(note_camera=Subquery(cam_notes.values('image')[:1]))
    probes = probes.annotate(note_raster=Subquery(raster_notes.values('image')[:1]))

    # REP SITE
    traj = TrajectoryEstimate.objects.filter(
        provenance=10, x=-2243, y=-2000,
        probe_insertion__session__subject__projects__name='ibl_neuropixel_brainwide_01',
        probe_insertion__session__qc__lt=50)

    labs = Lab.objects.all()
    labs = labs.annotate(
        nrep=Count('subject__actions_sessions__probe_insertion__trajectory_estimate',
                   filter=Q(subject__actions_sessions__probe_insertion__trajectory_estimate__in=traj)))

    context = {
        "total": traj.count(),
        "labs": labs,
        "traj": traj,
        "probes": probes,
        "MEDIA_URL": MEDIA_URL
        # "zip_var": zip(probes, cam_notes)
    }

    return HttpResponse(template.render(context, request))

# Q1 : how to link item to insertion when they relate to session
# Q2 : how to put new fields in (e.g. result of test for datasets)


'''
from django.db.models import Count, Q, Subquery, OuterRef
from experiments.models import TrajectoryEstimate, ProbeInsertion
from misc.models import Lab, Note
# BRAINWIDE INSERTIONS
probes = ProbeInsertion.objects.filter(
    session__subject__projects__name='ibl_neuropixel_brainwide_01',
    session__qc__lt=50)
cam_notes = Note.objects.filter(text__icontains='Camera images', object_id=OuterRef('session'))
raster_notes = Note.objects.filter(text__icontains='Drift', object_id=OuterRef('pk'))
probes = probes.annotate(note_cam=Subquery(cam_notes.values('image')[:1]))
probes = probes.annotate(note_raster=Subquery(raster_notes.values('image')[:1]))
'''

# cam_notes = []
# for pi in probes:
#     note = pi.session.notes.filter(text__icontains='Camera images').first()
#     if note is None:
#         url = 'https://upload.wikimedia.org/wikipedia/commons/4/45/Carré_rouge.svg'
#     else:
#         url = note.image.url
#     cam_notes.append(url)
#
# context = {
#     "total": traj.count(),
#     "labs": labs,
#     "traj": traj,
#     "pins": probes,
#     "zip_var": zip(probes, cam_notes)
# }

