from json import dump
import logging

from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from django.core.management.base import BaseCommand

from actions.models import (OtherAction, Session, Surgery, Weighing,
                            WaterRestriction, WaterAdministration)
from subjects.models import (Project, BreedingPair, GenotypeTest, Litter,
                             SubjectRequest, Zygosity, Allele, Line, Sequence,
                             Source, Species, Strain)
from misc.models import LabMember, LabLocation, Note

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export IBL data"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        proj = Project.objects.filter(name__icontains='ibl').first()

        # subjects in IBL
        subjects = proj.subject_set.all()

        # Subjects.
        objects = serialize('python', subjects)

        # Generic objects.
        objects.extend(serialize('python', Allele.objects.all()))
        objects.extend(serialize('python', Line.objects.all()))
        objects.extend(serialize('python', Sequence.objects.all()))
        objects.extend(serialize('python', Source.objects.all()))
        objects.extend(serialize('python', Species.objects.all()))
        objects.extend(serialize('python', Strain.objects.all()))

        # Misc.
        objects.extend(serialize('python', LabMember.objects.all()))
        objects.extend(serialize('python', LabLocation.objects.all()))

        # Actions and some subjects models.
        classes = (OtherAction, Session, Surgery, WaterAdministration, WaterRestriction,
                   Weighing, Zygosity, SubjectRequest, Litter, GenotypeTest)
        for cls in classes:
            qs = cls.objects.filter(subject__in=subjects)
            objects.extend(serialize('python', qs))
        objects.extend(serialize(
            'python', BreedingPair.objects.filter(litter__subject__in=subjects)))

        # Notes related to any of the previous objects.
        ids = set(obj['pk'] for obj in objects)
        objects.extend(serialize('python', Note.objects.filter(object_id__in=ids)))

        with open('dump_ibl.json', 'w') as f:
            dump(objects, f, cls=DjangoJSONEncoder, indent=1, sort_keys=True)
