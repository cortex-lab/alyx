# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2017-03-02 10:20
from __future__ import unicode_literals
import os.path as op
import re
import sys

from dateutil.parser import parse as parse_
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import migrations
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware

from actions.models import Surgery
from subjects.models import Species, Subject, Line, GenotypeTest, Sequence, Litter, Cage

from core import DATA_DIR, get_table, get_sheet_doc, sheet_to_table


# Functions
# ------------------------------------------------------------------------------------------------

def parse(date_str):
    date_str = date_str.strip() if date_str is not None else date_str
    if not date_str or date_str == '-':
        return
    ret = parse_(date_str)
    if not is_aware(ret):
        ret = make_aware(ret)
    return ret


def get_user(initials):
    nickname = {
        'AL': 'armin',
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
    return User.objects.get(username=nickname)


def get_line(sheet_name, table_line=None):
    name = {row['Sheet Name']: row['NAME'] for row in table_line}[sheet_name]
    return Line.objects.get(name=name)


def get_subject(nickname):
    if not nickname:
        return
    return Subject.objects.get(nickname=nickname)


# Import 1
# ------------------------------------------------------------------------------------------------

def get_line_kwargs(row):
    return dict(
        name=row['NAME'],
        auto_name=row['Autoname'],
        target_phenotype=row['LONG NAME'],
        description=row['BLURB'],
        json={"stock_no": row['STOCK NO'],
              "source": row['SOURCE'],
              "genotype": row['GENOTYPE'],
              "bru_strain_number": row['BRU STRAIN NUMBER'],
              "atlas": row['ATLAS'],
              "sheet_name": row['Sheet Name'],  # Used to find the worksheet in the Google Sheet
              }
    )


def import_procedure_subject(row, mouse=None, table_line=None):
    # Lookup severity.
    sc = Subject.SEVERITY_CHOICES
    severity = {v: k for (k, v) in dict(sc).items()}.get(row['Actual Severity'], '')

    # New or existing subject?
    ts_name = row['transgenic spreadsheet mouse name']
    subjects = Subject.objects.filter(nickname=ts_name) if ts_name else None
    if ts_name and subjects:
        subject = subjects[0]
        print("Updating existing subject %s." % ts_name)
    else:
        subject = Subject(nickname=row['Nickname'],
                          birth_date=parse(row['Date of Birth']),
                          )
        print("Creating new subject %s." % row['Nickname'])

    # Set/override the fields.
    kwargs = dict(
         nickname=row['Nickname'],
         adverse_effects=row['Adverse Effects'],
         death_date=parse(row['Cull Date']),
         cull_method=row['Cull Method'],
         actual_severity=severity,
         protocol_number=row['Protocol #'],
         responsible_user=get_user(row['Responsible User']),
         species=mouse,
         line=get_line(row['Line'], table_line=table_line),
     )
    for k, v in kwargs.items():
        setattr(subject, k, v)
    subject.save()

    # Create the surgery.
    kwargs = dict(
        users=[get_user(initials.strip())
               for initials in re.split(',|/', row['Surgery Performed By'])],
        subject=subject,
        start_time=parse(row['Date of surgery']),
        outcome_type=row['Acute/ Recovery'][0],
        narrative=row['Procedures'],
    )
    surgery = Surgery(**kwargs)
    surgery.save()


# Import 2
# ------------------------------------------------------------------------------------------------

def get_line_doc():
    return get_sheet_doc('Mice Stock - C57 and Transgenic')


def import_line(sheet):
    cols = sheet.row_values(3)
    line_name = sheet.title.strip()
    genotype_cols = [c[8:].strip() for c in cols if c.startswith('Genotype')]
    # Get or create line's sequences.
    sequences = {name: Sequence.objects.get_or_create(informal_name=name)[0]
                 for name in genotype_cols if name}
    # Get the existing line using the sheet name, or create a new line.
    lines = Line.objects.filter(json__sheet_name=line_name)
    if not lines:
        line = Line.objects.create(name=line_name)
    else:
        line = lines[0]
    line.sequences = list(sequences.values())
    print("Set line %s with %d sequences." % (line_name, len(sequences)))

    mouse = Species.objects.get(display_name='Laboratory mouse')

    # Importing the subjects.
    table = sheet_to_table(sheet)
    subjects = []
    for row in table:
        # Skip rows with empty autonames.
        if not row['autoname']:
            continue
        kwargs = {}
        kwargs['ear_mark'] = row['Ear mark']
        kwargs['sex'] = row['Sex']
        kwargs['notes'] = row['Notes']
        kwargs['birth_date'] = parse(row['DOB'])
        kwargs['death_date'] = parse(row.get('death date', None))
        kwargs['wean_date'] = parse(row.get('Weaned', None))
        kwargs['nickname'] = row['autoname']
        kwargs['json'] = {k: row[k] for k in ('LAMIS Cage number', 'F Parent', 'M Parent')}
        kwargs['line'] = line
        kwargs['species'] = mouse

        # Create the subject.
        subject, _ = Subject.objects.get_or_create(**kwargs)

        # Set the genotype.
        for c in cols:
            if not c.startswith('Genotype'):
                continue
            test_result = row[c]
            if test_result not in ('-', '+'):
                continue
            test_result = '-+'.index(test_result)
            # Get the sequence.
            sequence = sequences[c[8:].strip()]
            # Set the genotype test.
            gt, _ = GenotypeTest.objects.get_or_create(subject=subject,
                                                       sequence=sequence,
                                                       test_result=test_result)
        subject.save()
        subjects.append(subject)
    print("Added %d subjects." % len(subjects))

    # Set the litters.
    for subject in subjects:
        mother = subject.json['F Parent']
        father = subject.json['M Parent']
        litter, _ = Litter.objects.get_or_create(line=line,
                                                 birth_date=subject.birth_date,
                                                 notes='mother=%s\nfather=%s' % (mother, father),
                                                 )
        subject.litter = litter
        subject.save()

    # Set autoname index.
    if table:
        line.subject_autoname_index = int(table[-1].get('n', '') or 0)

    line.save()


# Migrations
# ------------------------------------------------------------------------------------------------

def load_static(apps, schema_editor):
    path = op.join(DATA_DIR, 'dumped_static.json')
    call_command('loaddata', path)


def make_admin(apps, schema_editor):
    for user in User.objects.all():
        user.is_superuser = True
        user.save()


def load_worksheets_1(apps, schema_editor):
    table_line = get_table('Mice Stock - C57 and Transgenic', 'Current lines in the unit',
                           header_line=0, first_line=2)

    # Add lines.
    Line.objects.bulk_create(Line(**get_line_kwargs(row)) for row in table_line)
    print("%d lines added." % len(table_line))


def load_worksheets_2(apps, schema_editor):
    doc = get_line_doc()
    sheets = doc.worksheets()[7:]
    for sheet in sheets:
        print("Importing line %s..." % sheet.title.strip())
        import_line(sheet)


def load_worksheets_3(apps, schema_editor):
    mouse = Species.objects.get(display_name='Laboratory mouse')
    table_subjects = get_table('Mice Procedure Log', 'PROCEDURE LOG',
                               header_line=0, first_line=2)
    table_line = get_table('Mice Stock - C57 and Transgenic', 'Current lines in the unit',
                           header_line=0, first_line=2)
    # Add subjects from procedure log.
    for row in table_subjects:
        if not row['Nickname']:
            continue
        import_procedure_subject(row,
                                 mouse=mouse,
                                 table_line=table_line,
                                 )


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('actions', '__latest__'),
        ('contenttypes', '__latest__'),
    ]

    operations = [
        migrations.RunPython(load_static),
        migrations.RunPython(make_admin),
        migrations.RunPython(load_worksheets_1),
        migrations.RunPython(load_worksheets_2),
        migrations.RunPython(load_worksheets_3),
    ]
