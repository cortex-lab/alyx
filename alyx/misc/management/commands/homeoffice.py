import contextlib
import logging
import sys

from django.core.management.base import BaseCommand
from django.db.models import Q

from subjects.models import Subject

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')


def assigned_to_stock_managers():
    return Q(responsible_user__is_stock_manager=True)


def assigned_to_no_one():
    return Q(responsible_user__isnull=True)


def killed(start_date, end_date):
    return Q(death_date__gte=start_date, death_date__lte=end_date)


def genotyped(start_date, end_date):
    return Q(genotype_date__gte=start_date, genotype_date__lte=end_date)


def not_used(query):
    return query.filter(assigned_to_stock_managers() |
                        assigned_to_no_one()).exclude(protocol_number='3')


def used(query):
    return (query.filter(protocol_number='3') |
            query.exclude(assigned_to_stock_managers() | assigned_to_no_one()))


def transgenic(query):
    return query.exclude(line__auto_name='C57')


@contextlib.contextmanager
def redirect_stdout(stream):
    import sys
    sys.stdout = stream
    yield
    sys.stdout = sys.__stdout__


def display(title, query):
    with open('homeoffice/%s.txt' % title, 'w') as f:
        with redirect_stdout(f):
            print("%s: %d subjects." % (title, len(query)))
            print('\t'.join(('#   ', 'user       ', 'prot.', 'death    ',
                             'genotyped', 'EM', 'nickname')))
            for i, subj in enumerate(query):
                print('\t'.join(('%04d' % (i + 1),
                                 '{0: <12}'.format(subj.responsible_user.username),
                                 subj.protocol_number,
                                 str(subj.death_date or ' ' * 10),
                                 str(subj.genotype_date or ' ' * 10),
                                 subj.ear_mark,
                                 subj.nickname,
                                 )))
            print('\n\n')


class Command(BaseCommand):
    help = ("Display information required by Home Office about number of animals used "
            "for research.")

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('start_date', type=str)
        parser.add_argument('end_date', type=str)

    def handle(self, *args, **options):
        start_date = options.get('start_date')
        end_date = options.get('end_date')

        k = Subject.objects.filter(killed(start_date, end_date)).order_by('death_date')
        g = Subject.objects.filter(genotyped(start_date, end_date)).order_by('genotype_date')

        print("Between %s and %s" % (start_date, end_date))

        display("Killed and not used", not_used(k))
        display("Genotyped and not used", not_used(g))
        display("Transgenic killed", transgenic(k))
        display("Killed and used", used(k))
        display("Genotyped and used", used(g))
        display("Negative genotyped and used", [s for s in used(g) if s.is_negative()])
        display("Genotyped, killed, and not used", not_used(g & k))
        display("Transgenic killed, not genotyped, and not used",
                transgenic(not_used(k)).exclude(genotyped(start_date, end_date)))
