import logging
import sys

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from subjects.models import Subject

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')


class Command(BaseCommand):
    help = ("Display information required by Home Office about number of animals used "
            "for research.")

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('start_date', type=str)
        parser.add_argument('end_date', type=str)

    def handle(self, *args, **options):
        s = Subject.objects.filter(Q(responsible_user__username__in=settings.STOCK_MANAGERS) |
                                   Q(responsible_user__isnull=True))
        s = s.exclude(protocol_number='3')

        start_date = options.get('start_date')
        end_date = options.get('end_date')

        killed = s.filter(death_date__gte=start_date,
                          death_date__lte=end_date).order_by('death_date')
        genotyped = s.filter(genotype_date__gte=start_date,
                             genotype_date__lte=end_date).order_by('genotype_date')

        self.stdout.write("Between %s and %s" % (start_date, end_date))
        self.stdout.write("Animals killed: %d" % len(killed))
        self.stdout.write("Animals genotyped: %d" % len(genotyped))

        for (title, subjects) in [('killed', killed), ('genotyped', genotyped)]:
            self.stdout.write("\nAnimals %s:" % title)
            i = 1
            for subj in subjects:
                self.stdout.write("%d\t%s\t%s\t%s\t%s\t%s" % (
                    i,
                    subj.responsible_user,
                    subj.protocol_number,
                    '%s: %s' % (title,
                                subj.death_date if title == 'killed' else subj.genotype_date),
                    subj.ear_mark,
                    subj.nickname,
                ))
                i += 1
