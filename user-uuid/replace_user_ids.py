#!/usr/bin/env python3

import os
import os.path as op
import sys
import json
import uuid
import re


if len(sys.argv) > 1 and sys.argv[1] == 'test':
    path = '../data/all_dumped_anon.json'
    out = '../data/all_dumped_anon.uuid.json'
else:
    path = 'dump.json'
    out = 'dump.uuid.json'

user_keys = {}

if op.exists('user_keys.json'):
    with open('user_keys.json', 'r') as f:
        user_keys.update({int(key): value for key, value in json.load(f).items()})


"""
actions.ProcedureType.user
actions.WaterAdministration.user
actions.BaseAction.users

data.DatasetType.created_by
data.BaseExperimentalData.created_by

misc.Note.user

subjects.Project.users
subjects.Subject.responsible_user
subjects.SubjectRequest.user


user
created_by
responsible_user
users

NOTE:
groups should not be dumped, but set up locally with a management command

"""

# Load the database dump.
with open(path, 'r') as f:
    db = json.load(f)


# Generate and replace, if needed, the user UUID.
for item in db:
    if item['model'] != 'auth.user':
        continue
    old_pk = item['pk']
    # Remove the groups.
    item['fields'].pop('groups', [])
    item['fields'].pop('user_permissions', [])
    if isinstance(old_pk, int):
        if not user_keys.get(old_pk, None):
            key = str(uuid.uuid4())
            user_keys[old_pk] = key
        item['model'] = 'misc.LabMember'
        item['pk'] = user_keys[old_pk]


users = [item for item in db if item['model'] == 'auth.user']
assert all(isinstance(user['pk'], str) for user in users)


# Replace the relationships.
to_remove = []
for i, item in enumerate(db):
    for field, value in item['fields'].items():
        if field in ('user', 'created_by', 'responsible_user'):
            if value is None:
                continue
            assert isinstance(value, int)
            new_pk = user_keys[value]
            item['fields'][field] = new_pk
            assert isinstance(item['fields'][field], str)
        elif field == 'users':
            value = item['fields'][field]
            item['fields'][field] = [user_keys[pk] for pk in value]
            assert all(isinstance(_, str) for _ in item['fields'][field])

    # Mark some items to remove.
    if item['model'] == 'subjects.species':
        to_remove.append(i)
    if (item['model'] in ('data.dataformat', 'data.datasettype') and
            item['fields']['name'] == 'unknown'):
        to_remove.append(i)
    if item['model'] == 'subjects.stockmanager':
        to_remove.append(i)


# Remove items that are automatically created by the migrations.
for i in sorted(to_remove, reverse=True):
    db.pop(i)


# Check the change worked.
for item in db:
    for field, value in item['fields'].items():
        if 'superuser' in field or 'permission' in field:
            continue
        if 'user' in field or 'created_by' in field:
            if isinstance(value, list):
                assert all(isinstance(_, str) for _ in value)
            else:
                assert value is None or isinstance(value, str)


# Integrity check: remove non-existing foreign keys.
pks = set(item['pk'] for item in db)
UUID_REGEX = r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
missing = []
for item in db:
    fields_to_remove = []
    for field, value in item['fields'].items():
        if field == 'md5' or 'globus' in field:
            continue
        # Foreign keys.
        if isinstance(value, str):
            if re.match(UUID_REGEX, value):
                if value not in pks:
                    assert field in ('species, data_format, dataset_type')
                    fields_to_remove.append(field)
                    missing.append((item, field, value))
        # Many-to-many relationships.
        if isinstance(value, list):
            for _ in value:
                if re.match(UUID_REGEX, str(_)):
                    if _ not in pks:
                        assert field in ('species, data_format, dataset_type')
                        fields_to_remove.append(field)
                        missing.append((item, field, _))
    for f in fields_to_remove:
        item['fields'].pop(f, None)
    fields_to_remove = []
missing_pks = set(pk for (item, field, pk) in missing)
missing_item_field = set((item['model'], field) for (item, field, _) in missing)


# Save the database dump.
with open(out, 'w') as f:
    json.dump(db, f, indent=1)


'''
with open('user_keys.json', 'w') as f:
    json.dump(user_keys, f, indent=1)
'''
