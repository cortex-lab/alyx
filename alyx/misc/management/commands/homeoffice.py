import contextlib
import logging
import os
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


def born(start_date, end_date):
    return Q(birth_date__gte=start_date, birth_date__lte=end_date)


def killed(start_date, end_date):
    return Q(death_date__gte=start_date, death_date__lte=end_date)


def genotyped(start_date, end_date):
    return Q(genotype_date__gte=start_date, genotype_date__lte=end_date)


def not_used(query):
    return query.filter(Q(actions_surgerys__isnull=True)).distinct()


def used(query):
    return query.filter(actions_surgerys__isnull=False).distinct()


def transgenic(query):
    return query.exclude(line__nickname='C57')


@contextlib.contextmanager
def redirect_stdout(stream):
    import sys
    sys.stdout = stream
    yield
    sys.stdout = sys.__stdout__


def display(title, query):
    os.makedirs('homeoffice', exist_ok=True)
    path = 'homeoffice/%s.txt' % title
    with open(path, 'w') as f:
        with redirect_stdout(f):
            print("%s: %d subjects." % (title, len(query)))
            print('\t'.join(('#   ', 'user       ', 'prot.',
                             'born     ',
                             'genotyped',
                             'died     ',
                             'EM', 'nickname')))
            for i, subj in enumerate(query):
                print('\t'.join(('%04d' % (i + 1),
                                 '{0: <12}'.format(subj.responsible_user.username),
                                 subj.protocol_number,
                                 str(subj.birth_date or ' ' * 10),
                                 str(subj.genotype_date or ' ' * 10),
                                 str(subj.death_date or ' ' * 10),
                                 subj.ear_mark,
                                 subj.nickname,
                                 )))
            print('\n\n')
    os.system('expand -t 4 "%s" | sponge "%s"' % (path, path))


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

        k = Subject.objects.filter(killed(start_date, end_date)).order_by('cull__date')
        g = Subject.objects.filter(genotyped(start_date, end_date)).order_by('genotype_date')
        tkg = transgenic(k & g)

        print("Between %s and %s" % (start_date, end_date))

        display("All animals", Subject.objects.all().order_by('nickname'))
        display("Transgenic killed", transgenic(k))
        display("Killed and used", used(k))

        display("Transgenic killed and genotyped", tkg)
        display("Transgenic killed and genotyped (negative)", [s for s in tkg if s.is_negative()])
        display("Transgenic killed and genotyped (not used)", not_used(tkg))

        display("Genotyped and used", used(g))

        tkng = transgenic(k).exclude(genotyped(start_date, end_date))
        display("Transgenic killed and not genotyped", tkng)
