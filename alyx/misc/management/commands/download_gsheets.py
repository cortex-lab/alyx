from collections import OrderedDict
import json
import logging
from operator import itemgetter
import os
import os.path as op
from pickle import load, dump
import re
import uuid

from datetime import datetime
from django.utils import timezone
from dateutil.parser import parse as parse_
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz

from django.core.management.base import BaseCommand
from django.core.management import call_command


logger = logging.getLogger(__name__)


SEVERITY_CHOICES = (
    (1, 'Sub-threshold'),
    (2, 'Mild'),
    (3, 'Moderate'),
    (4, 'Severe'),
    (5, 'Non-recovery'),
)


def warn(*args):
    args += ('\033[0m',)
    print('\033[1;31m', *args)


def pad(s):
    if not s:
        return ''
    return re.sub(r'\_([0-9]+)$', lambda m: '_%04d' % int(m.group(1)), s)


def flatten(l):
    return [item for sublist in l for item in sublist]


def get_username(initials):
    return {
        'AL': 'armin',
        'ALK': 'armin',
        'AP': 'andy',
        'CR': 'charu',
        'NS': 'nick',
        'JL': 'julie',
        'ICL': 'i-chun',
        'PZH': 'peter',
        'MDia': 'mika',
        'MK': 'michael',
        'SF': 'sam',
        'MP': 'marius',
        'PC': 'pip',
        'MW': 'miles',
        'LF': 'laura',
    }[initials]


def parse(date_str, time=False):
    date_str = date_str.strip() if date_str is not None else date_str
    if not date_str or date_str == '-':
        return ''
    try:
        ret = parse_(date_str)
    except:
        logger.warn("Could not parse date %s.", date_str)
        return ''
    if not time:
        return ret.strftime("%Y-%m-%d")
    ret = ret.replace(tzinfo=pytz.UTC)
    return ret.isoformat()


def _parse_float(x):
    if not x:
        return None
    if x.lower() in ('-', 'free water', 'free'):
        return None
    x = float(x)
    return x


def get_sheet_doc(doc_name):
    scope = ['https://spreadsheets.google.com/feeds']
    path = op.join(DATA_DIR, 'gdrive.json')
    credentials = ServiceAccountCredentials.from_json_keyfile_name(path, scope)
    gc = gspread.authorize(credentials)
    return gc.open(doc_name)


def _load(fn):
    with open(op.join(DATA_DIR, fn), 'rb') as f:
        return load(f)


def _dump(obj, fn):
    with open(op.join(DATA_DIR, fn), 'wb') as f:
        dump(obj, f)


class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


def sheet_to_table(wks, header_line=0, first_line=2):
    print("Downloading %s..." % wks)
    rows = wks.get_all_values()
    table = []
    headers = rows[header_line]
    for row in rows[first_line:]:
        l = {headers[i].strip(): row[i].strip() for i in range(len(headers))}
        # Empty line = end of table.
        if all(_ == '' for _ in l.values()):
            break
        table.append(Bunch(l))
    return table


def make_fixture(model, data, name_field='name', path=None):
    def _transform(k, v):
        if k.endswith('_date') and not v:
            return None
        return v

    def _gen():
        for item in data.values() if isinstance(data, dict) else data:
            pk = item.get('pk', None) if isinstance(item, dict) else None
            yield OrderedDict((
                ('model', model),
                ('pk', pk),
                ('fields', ({k: _transform(k, v) for k, v in item.items() if k != 'pk'}
                            if isinstance(item, dict)
                            else {name_field: item})),
            ))
    with open(op.join(DATA_DIR, 'json', (path or model) + '.json'), 'w') as f:
        json.dump(list(_gen()), f, indent=2)


class GoogleSheetImporter(object):
    _table_names = ('procedure_table',
                    'current_lines_table',
                    'line_tables',
                    'breeding_pairs_table',
                    'water_tables',
                    'water_info',
                    )

    def __init__(self):
        if not op.exists(op.join(DATA_DIR, 'dumped_google_sheets.pkl')):
            self._download_tables()
            self._cache_tables()
        self._load_tables()

        self.strains = self._get_strains(self.current_lines_table)
        self.alleles = self._get_alleles()
        self.lines = self._get_lines(self.current_lines_table)
        self.sequences = self._get_sequences(self.line_tables)
        self.subjects = self._get_subjects(self.line_tables)
        self.litters = self._get_litters(self.subjects)
        self._set_autoname_indices(self.line_tables)
        self.surgeries = self._get_surgeries(self.procedure_table)
        self.breeding_pairs = self._get_breeding_pairs(self.breeding_pairs_table)
        self.litter_breeding_pairs = self._get_litter_breeding_pairs()
        self.genotype_tests = self._get_genotype_tests()
        self._add_water_info()
        self.restrictions, self.weighings = self._add_water_restriction()
        self.administrations = self._add_water_administrations()

    def _download_tables(self):
        self._line_doc = get_sheet_doc('Mice Stock - C57 and Transgenic')
        self._procedure_doc = get_sheet_doc('Mice Procedure Log')
        self._water_doc = get_sheet_doc('Water control')

        # Load the procedure table.
        print("Downloading the procedure table...")
        self.procedure_table = sheet_to_table(self._procedure_doc.worksheet('PROCEDURE LOG'))

        # Load the current lines in the unit table.
        print("Downloading the current lines table...")
        self.current_lines_table = sheet_to_table(self._line_doc.worksheet('Current lines in the '
                                                                           'unit'))

        # Load all line sheets into tables.
        line_sheets = self._line_doc.worksheets()[7:]
        self.line_tables = {}
        for sheet in line_sheets:
            n = sheet.title.strip()
            print("Downloading the %s table..." % n)
            self.line_tables[n] = sheet_to_table(sheet, header_line=2, first_line=3)

        # Load the breeding pairs table.
        print("Downloading the breeding pairs table...")
        self.breeding_pairs_table = sheet_to_table(self._line_doc.worksheet('Breeding Pairs'),
                                                   header_line=2, first_line=3)

        # Load all subject water sheets into tables.
        water_sheets = self._water_doc.worksheets()
        self.water_tables = {}
        self.water_info = {}
        for sheet in water_sheets:
            n = sheet.title.strip()
            if n == '<mouseID>':
                break
            print("Downloading the %s table..." % n)
            # Water restrictions.
            wrs = []
            for i in range(4):
                start_date = sheet.acell('A%d' % (9 + i)).value
                end_date = sheet.acell('G%d' % (9 + i)).value
                weight = sheet.acell('D%d' % (9 + i)).value
                if not start_date:
                    break
                wrs.append(Bunch(start_date=start_date, weight=weight, end_date=end_date))
            self.water_info[n] = {
                'sex': sheet.acell('C4').value,
                'birth_date': sheet.acell('C5').value,
                'implant_weight': sheet.acell('C6').value,
                'water_restrictions': wrs,
            }
            self.water_tables[n] = sheet_to_table(sheet, header_line=13, first_line=14)
            # HACK: empty header = header is "type"
            for row in self.water_tables[n]:
                row['Type'] = row.pop('', None)

    def _cache_tables(self):
        _dump({n: getattr(self, n) for n in self._table_names}, 'dumped_google_sheets.pkl')

    def _load_tables(self):
        for n, v in _load('dumped_google_sheets.pkl').items():
            setattr(self, n, v)

    def _get_strains(self, table):
        return sorted(set(row['strain'] for row in table if row.get('strain', None)))

    def _get_alleles(self):
        return ["Ai32-ChR2", "DAT-Cre", "Drd1a-Cre", "Emx1-Cre", "Gad-Cre", "KHA1-KO",
                "Ai95-G6f", "Ntsr1-Cre", "Pv-Cre", "Sst-Cre", "Snap26-G6s", "TetO-G6s",
                "TdTom-Cre", "Thy18", "Vip-Cre", "Vglut1-Cre", "Ai78-VSFP", "Ai93-G6f",
                "Ai94-G6s", "Ai148-G6f", "Rasgrf-Cre", "Camk2a-tTa"]

    def _get_lines(self, table):
        """Dict of lines indexed by sheet name."""
        lines = {}
        for row in table:
            if not row['Sheet Name']:
                continue
            fields = Bunch()
            fields['name'] = row['NAME']
            fields['auto_name'] = row['Autoname']
            fields['target_phenotype'] = row['LONG NAME']
            fields['description'] = row['BLURB']
            fields['strain'] = [row['strain']] if row['strain'] else None
            fields['json'] = {
                "stock_no": row['STOCK NO'],
                "source": row['SOURCE'],
                "genotype": row['GENOTYPE'],
                "bru_strain_number": row['BRU STRAIN NUMBER'],
                "atlas": row['ATLAS'],
            }
            lines[row['Sheet Name']] = fields
        return lines

    def _get_line_sequences(self, line_table):
        if not line_table:
            return
        return sorted(set(c[8:].strip() for c in line_table[0].keys()
                          if c.startswith('Genotype') and c[8:].strip()))

    def _get_sequences(self, line_tables):
        """Set each line's sequences and return the list of all sequences."""
        seqs = []
        for name, line_table in line_tables.items():
            sequences = self._get_line_sequences(line_table)
            self.lines[name]['sequences'] = [[_] for _ in sequences]
            seqs.append(sequences)
        return sorted(set(flatten(seqs)))

    def _get_genotype_test(self, row):
        # row from line table
        for col, val in row.items():
            if not col.startswith('Genotype'):
                continue
            if val not in ('-', '+'):
                continue
            test_result = '-+'.index(val)
            sequence = col[8:].strip()
            yield {'sequence': sequence,
                   'test_result': test_result,
                   }

    def _get_litter_notes(self, row):
        mother = row.get('F Parent', '')
        father = row.get('M Parent', '')
        notes = 'mother=%s\nfather=%s' % (mother, father)
        return notes

    def _get_subjects_in_line(self, line, table):
        line_name = self.lines[line].auto_name
        logger.debug("Importing subjects from line %s.", line_name)
        subjects = {}
        for i, row in enumerate(table):
            fields = Bunch()
            fields['ear_mark'] = row['Ear mark']
            fields['sex'] = row['Sex']
            fields['notes'] = row['Notes']
            fields['birth_date'] = parse(row['DOB'])
            fields['death_date'] = parse(row.get('Death date', None))
            fields['wean_date'] = parse(row.get('Wean date', None))

            if i == 0:
                if 'Death date' not in row:
                    warn("No death date in line %s." % line_name)
                if 'Wean date' not in row:
                    warn("No wean date in line %s." % line_name)

            # New fields.
            fields['genotype_date'] = parse(row.get('G.type date', None))
            fields['to_be_genotyped'] = True if row.get('To be g.typed', None) else False
            fields['to_be_culled'] = True if row.get('To be culled', None) else False
            fields['reduced'] = True if row.get('Reduced', None) else False

            for n in ('Animal name', 'animal name', 'Animal number'):
                if row.get(n):
                    fields['nickname'] = pad(row[n].strip())
                    break
            # Empty nickname? End of the table.
            if 'nickname' not in fields:
                warn("Skip empty subject in %s with DOB %s." % (line, row['DOB']))
                break
            fields['lamis_cage'] = (int(re.sub("[^0-9]", "", row['LAMIS Cage number']))
                                    if row['LAMIS Cage number'] else None)
            fields['line'] = [line_name]
            litter_notes = self._get_litter_notes(row)
            fields['litter'] = (line_name, fields['birth_date'], litter_notes)
            fields['genotype_test'] = list(self._get_genotype_test(row))
            # Temporary values used later on.
            bp_index = row.get('BP #', None)
            if bp_index:
                try:
                    fields['bp_index'] = int(bp_index)
                except ValueError:
                    warn("BP # is not an int: %s for subject %s.",
                         bp_index, fields['nickname'])
            logger.info("Add subject %s.", fields['nickname'])
            subjects[fields['nickname']] = fields
        return subjects

    def _get_subjects(self, line_tables):
        subjects = {}
        for line, table in line_tables.items():
            subjects.update(self._get_subjects_in_line(line, table))
        return subjects

    def _get_line(self, line):
        out = self.lines.get(line, None)
        if not out:
            for l in self.lines.values():
                if l.auto_name == line:
                    return l
        return out

    def _get_litters(self, subjects):
        """Return a set of unique tuples (line, birth_date, notes)."""
        litters_set = sorted(set([subject.litter for subject in subjects.values()]),
                             key=itemgetter(1))
        litters = {}
        litter_map = {}
        for line, birth_date, notes in litters_set:
            # Find the litter name.
            for i in range(1, 1000):
                name = '%s_L_%03d' % (line, i)
                if name in litters:
                    continue
                break
            litters[name] = Bunch(descriptive_name=name,
                                  line=[line],
                                  birth_date=birth_date,
                                  notes=notes,
                                  pk=uuid.uuid4().hex,
                                  )
            self._get_line(line)['litter_autoname_index'] = i
            litter_map[line, birth_date, notes] = name
        # Replace the litter tuples by the litter names.
        for subject in subjects.values():
            subject.litter = [litter_map[subject.litter]]
        return litters

    def _set_autoname_indices(self, line_tables):
        for line, table in line_tables.items():
            try:
                self.lines[line]['subject_autoname_index'] = int(table[-1].get('n', '') or 0)
            except ValueError:
                warn("Unable to set subject_autoname_index for %s." % line)

    def _get_severity(self, severity_name):
        for s, n in SEVERITY_CHOICES:
            if n == severity_name:
                return s

    def _get_surgeries(self, table):
        surgeries = []
        for row in table:
            old_name = pad(row['transgenic spreadsheet mouse name'])
            new_name = pad(row['Nickname'])
            new_name = new_name if new_name not in (None, '', '-') else old_name
            birth_date = parse(row['Date of Birth'])
            # Get or create the subject.
            if old_name not in self.subjects:
                warn(("Subject %s doesn't exist in the transgenic spreadsheet. "
                      "The nickname is %s and date of surgery is %s."
                      ) % (old_name, new_name, row['Date of surgery']))
            else:
                logger.debug("Rename %s to %s.", old_name, new_name)
            self.subjects[new_name] = self.subjects.pop(old_name, Bunch(birth_date=birth_date))
            # Update the subject name.
            subject = self.subjects[new_name]

            subject['nickname'] = new_name
            subject['actual_severity'] = self._get_severity(row['Actual Severity'])
            line = self.lines.get(row['Line'], None)
            if line:
                subject['line'] = [line.auto_name]
            else:
                warn("Line %s does not exist for subject %s in procedure log."
                     % (row['Line'], new_name))
            subject['adverse_effects'] = row['Adverse Effects']
            subject['death_date'] = parse(row['Cull Date'])
            subject['cull_method'] = row['Cull Method']
            subject['protocol_number'] = row['Protocol #']
            subject['responsible_user'] = [get_username(row['Responsible User'])]

            # Save the old nickname.
            date_time = datetime.now(timezone.utc).isoformat()
            subject['json'] = {'history': {'nickname': [
                {'date_time': date_time, 'value': old_name}
            ]}}

            # Add the surgery.
            surgery = Bunch()
            surgery['users'] = [[get_username(initials.strip())]
                                for initials in re.split(',|/', row['Surgery Performed By'])]
            surgery['subject'] = [new_name]
            surgery['start_time'] = parse(row['Date of surgery'], time=True)
            surgery['outcome_type'] = row['Acute/ Recovery'][0]
            surgery['narrative'] = row['Procedures']

            surgeries.append(surgery)
        return surgeries

    def _get_breeding_pairs(self, table):
        breeding_pairs = {}
        for i, row in enumerate(table):
            line = row['line']
            index = row['index'] or 0
            if not line:
                continue

            bp = Bunch()
            try:
                index = int(index)
            except ValueError:
                warn("BP # %s is not an integer in line %s in breeding pairs sheet." %
                     (index, line))
                continue
            bp['name'] = '%s_BP_%03d' % (line, index)
            bp['line'] = [line]
            bp['start_date'] = parse(row.get('Date together', None))
            bp['end_date'] = parse(row.get('Date ended', None))
            bp['notes'] = row['Notes']
            bp['json'] = {
                'father_genotype': row.get('Father Genotype', None),
                'mother_genotype': row.get('Mother Genotype', None),
                'animal_number_male': row.get('Animal # male', None),
                'animal_number_female': row.get('Animal # female', None),
            }

            if i == 0:
                if 'Date together' not in row:
                    warn("No start date in line %s." % line)
                if 'Date ended' not in row:
                    warn("No end date in line %s." % line)

            line_obj = self._get_line(line)
            if line_obj:
                line_obj['breeding_pair_autoname_index'] = index
            else:
                warn("Line %s referenced in BP %s doesn't exist."
                     % (line, bp['name']))

            for field, name_col, dob_col, sex in [('father', 'Father name', 'Father DOB', 'M'),
                                                  ('mother1', 'Mother 1 name', 'Mother DOB', 'F'),
                                                  ('mother2', 'Mother 2 name', '', 'F'),
                                                  ]:
                if not row[name_col]:
                    continue
                # Determine parent properties.
                name = pad(row[name_col])
                # Skip subjects with a ?.
                if '?' in name:
                    warn("Skipping subject %s in line %s." % (name, line))
                    continue
                parent = self.subjects.get(name, Bunch(nickname=name))
                parent['birth_date'] = parse(row[dob_col]) if dob_col else None
                parent['line'] = [line]
                parent['lamis_cage'] = int(row['LAMIS Cage #']) if row['LAMIS Cage #'] else None

                # Sanity check for sex.
                if 'sex' in parent and parent['sex'] != sex:
                    warn("Sex mismatch for %s between line sheet %s "
                         "and breeding pair sheet." % (name, line))
                parent['sex'] = sex

                # Make sure the parent is in the subjects dictionary.
                self.subjects[name] = parent
                bp[field] = [name]

            breeding_pairs[bp['name']] = bp

        return breeding_pairs

    def _get_litter_breeding_pairs(self):
        litter_bps = []
        litter_names = set()
        for subject in self.subjects.values():
            bp_index = subject.pop('bp_index', None)
            if not bp_index:
                continue
            line_name = subject['line'][0]
            bp_name = '%s_BP_%03d' % (line_name, bp_index)
            litter = subject['litter'][0]
            # Skip existing items.
            if litter in litter_names:
                continue
            item = self.litters[litter].copy()
            item['breeding_pair'] = [bp_name]
            litter_bps.append(item)
            litter_names.add(litter)
        return litter_bps

    def _get_genotype_tests(self):
        tests = []
        for subject in self.subjects.values():
            for test in subject.pop('genotype_test', []):
                tests.append(dict(
                    subject=[subject['nickname']],
                    sequence=[test['sequence']],
                    test_result=test['test_result'],
                ))
        return tests

    def _add_water_info(self):
        names = sorted(self.water_info)
        for n in names:
            info = self.water_info[n]
            # Skip non-existing subjects.
            if n not in self.subjects:
                del self.water_info[n]
                continue
            # Update the subject.
            subj = self.subjects[n]
            bd = parse(info['birth_date'])
            if subj['birth_date'] != bd:
                subj['birth_date'] = bd
            subj['implant_weight'] = float(info['implant_weight'])
            subj['sex'] = info['sex']

    def _add_water_restriction(self):
        weighings = []
        restrictions = []
        for n, info in self.water_info.items():
            if n not in self.subjects:
                continue
            for restriction in info['water_restrictions']:
                w = Bunch()
                r = Bunch()
                date = parse(restriction['start_date'], time=True)
                weight = restriction['weight']

                w['subject'] = [n]
                w['date_time'] = date
                w['weight'] = weight

                r['subject'] = [n]
                r['start_time'] = date
                r['end_time'] = parse(restriction['end_date'], time=True) or None

                weighings.append(w)
                restrictions.append(r)
        return restrictions, weighings

    def _add_water_administrations(self):
        administrations = []
        for n, table in self.water_tables.items():
            if n not in self.subjects:
                continue
            for row in table:
                # No date? end of the table.
                if 'Date' not in row:
                    warn("Water control sheet %s could not be imported." % n)
                    break
                date = row['Date']
                if not date:
                    break
                date = parse(date, time=True)

                try:
                    weight = _parse_float(row['weight (g)'])
                    water = _parse_float(row['Water (ml)'])
                    hydrogel = _parse_float(row['Hydrogel (g)'])
                except ValueError:
                    warn("One of the numbers in water admin sheet for %s is not "
                         "a float." % n)
                    continue

                # Add weighings.
                if weight is not None:
                    w = Bunch()
                    w['subject'] = [n]
                    w['date_time'] = date
                    w['weight'] = weight
                    self.weighings.append(w)

                # Add water administrations.
                if water:
                    a = Bunch()
                    a['subject'] = [n]
                    a['date_time'] = date
                    a['water_administered'] = water
                    a['hydrogel'] = False
                    administrations.append(a)

                if hydrogel:
                    a = Bunch()
                    a['subject'] = [n]
                    a['date_time'] = date
                    a['water_administered'] = hydrogel
                    a['hydrogel'] = True
                    administrations.append(a)

        return administrations


class Command(BaseCommand):
    help = "Imports Google Sheets data into the database"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('data_dir', nargs=1, type=str)

        parser.add_argument('-R', '--remove-pickle',
                            action='store_true',
                            dest='remove_pickle',
                            default=False,
                            help='Removes and redownloads dumped_google_sheets.pkl')

    def handle(self, *args, **options):
        global DATA_DIR
        DATA_DIR = options.get('data_dir')[0]

        if not op.isdir(DATA_DIR):
            self.stdout.write('Error: %s is not a directory' % DATA_DIR)
            return

        if options.get('remove_pickle'):
            try:
                os.remove(op.join(DATA_DIR, 'dumped_google_sheets.pkl'))
                self.stdout.write('Removed dumped_google_sheets.pkl')
            except FileNotFoundError:
                self.stdout.write(self.style.NOTICE(
                    'Could not remove dumped_google_sheets.pkl: file does not exist'))

        importer = GoogleSheetImporter()

        make_fixture('subjects.allele', importer.alleles, 'informal_name', path='01-allele')
        make_fixture('subjects.strain', importer.strains, 'descriptive_name', path='02-strain')
        make_fixture('subjects.sequence', importer.sequences, 'informal_name', path='03-sequence')
        make_fixture('subjects.line', importer.lines, 'auto_name', path='04-line')
        make_fixture('subjects.litter', importer.litters, 'descriptive_name', path='05-litter')
        make_fixture('subjects.subject', importer.subjects, 'nickname', path='06-subject')
        make_fixture('subjects.genotypetest', importer.genotype_tests, path='07-genotypetest')
        make_fixture('subjects.breedingpair', importer.breeding_pairs, 'name',
                     path='08-breedingpair')
        make_fixture('actions.surgery', importer.surgeries, path='09-surgery')
        make_fixture('subjects.litter', importer.litter_breeding_pairs,
                     path='10-litter-breedingpair')
        make_fixture('actions.waterrestriction', importer.restrictions,
                     path='11-water-restrictions')
        make_fixture('actions.weighing', importer.weighings, path='12-weighings')
        make_fixture('actions.wateradministration', importer.administrations,
                     path='13-water-administrations')

        json_dir = op.join(DATA_DIR, 'json')

        if not os.path.isdir(json_dir):
            self.stdout.write('Error: %s does not exist: it should contain .json files' % json_dir)
            return

        for root, dirs, files in os.walk(json_dir):
            for file in sorted(files):
                if file.endswith('.json'):
                    fullpath = op.join(json_dir, file)
                    call_command('loaddata', fullpath, verbosity=3, interactive=False)

        self.stdout.write(self.style.SUCCESS('Loaded all JSON files from %s' % json_dir))
