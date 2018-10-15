from django.core.management import BaseCommand
from subjects.models import (ZygosityFinder, ZygosityRule, Subject, Line, Allele, Sequence,
                             ZYGOSITY_SYMBOLS)


def _parse_rule(rule):
    string, res = rule
    out = {}
    for substr in string.split(','):
        if substr[0] == '-':
            sign = 0
            substr = substr[1:]
        else:
            sign = 1
        out[substr] = sign
    out['res'] = res
    return out


class Command(BaseCommand):
    help = "Updates all automatically generated zygosities from genotype tests"

    def add_arguments(self, parser):
        parser.add_argument('subjects', nargs='*',
                            help='Subject nicknames')
        parser.add_argument('--migrate_rules', action='store_true')
        parser.add_argument('--add_line_alleles', action='store_true')

    def handle(self, *args, **options):

        if options.get('add_line_alleles'):
            from collections import defaultdict
            lines = defaultdict(set)
            for subject in Subject.objects.all():
                if not subject.line:
                    continue
                alleles = subject.genotype.all()
                lines[subject.line].update([al for al in alleles])
            for line, alleles in lines.items():
                line.alleles.add(*alleles)
                return

        if options.get('migrate_rules'):
            from subjects.zygosities import ZYGOSITY_RULES
            for l, a, rules in ZYGOSITY_RULES:
                for rule in rules:
                    r = _parse_rule(rule)
                    zygosity = ZYGOSITY_SYMBOLS.index(r.pop('res'))
                    k = sorted(r.keys())
                    n = len(k)
                    seq0 = k[0]
                    res0 = r[seq0]
                    kwargs = dict(
                        line=Line.objects.get(nickname=l),
                        allele=Allele.objects.get(nickname=a),
                        sequence0=Sequence.objects.get_or_create(name=seq0)[0],
                        sequence0_result=res0,
                        zygosity=zygosity
                    )
                    if n >= 2:
                        seq1 = k[1]
                        res1 = r[seq1]
                        kwargs.update(dict(
                            sequence1=Sequence.objects.get_or_create(name=seq1)[0],
                            sequence1_result=res1
                        ))
                    try:
                        ZygosityRule.objects.create(**kwargs)
                    except Exception as e:
                        print(e)
            return

        zf = ZygosityFinder()

        self.stdout.write("Updating zygosities...")
        if options.get('subjects'):
            subjects = Subject.objects.filter(nickname__in=options.get('subjects'))
        else:
            subjects = Subject.objects.all()
        for subject in subjects:
            zf.genotype_from_litter(subject)
            zf.update_subject(subject)

        self.stdout.write(self.style.SUCCESS('Updated zygosities!'))
