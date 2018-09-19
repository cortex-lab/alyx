from json import dump
import logging

from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

from actions.models import (OtherAction, Session, Surgery, Weighing, ProcedureType,
                            WaterRestriction, WaterAdministration)
from subjects.models import (Project, BreedingPair, GenotypeTest, Litter,
                             SubjectRequest, Zygosity, Allele, Line, Sequence,
                             Source, Species, Strain, Subject)
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
        objects.extend(serialize('python', ProcedureType.objects.all()))

        # Misc.
        objects.extend(serialize('python', LabMember.objects.all()))
        objects.extend(serialize('python', LabLocation.objects.all()))

        # Actions and some subjects models.
        classes = (OtherAction, Session, Surgery, WaterAdministration, WaterRestriction,
                   Weighing, Zygosity, SubjectRequest, Litter, GenotypeTest)
        for cls in classes:
            qs = cls.objects.filter(subject__in=subjects)
            objects.extend(serialize('python', qs))

        # Breeding Pairs
        bp = BreedingPair.objects.filter(litter__subject__in=subjects)
        objects.extend(serialize('python', bp))

        # Subjects related to the BreedingPair are also necessary
        more_subjects = []
        if bp.count() > 0:
            for b in bp.values():
                more_subjects.append(b['father_id'])
                more_subjects.append(b['mother1_id'])
                more_subjects.append(b['mother2_id'])
            more_subjects = Subject.objects.filter(id__in=list(set(more_subjects)))
            objects.extend(serialize('python', more_subjects))


        # Notes related to any of the previous objects.
        ids = set(obj['pk'] for obj in objects)
        objects.extend(serialize('python', Note.objects.filter(object_id__in=ids)))

        # Groups at last but this doesn't have UUID
        objects.extend(serialize('python', Group.objects.all()))

        with open('dump_ucl.json', 'w') as f:
            dump(objects, f, cls=DjangoJSONEncoder, indent=1, sort_keys=True)
