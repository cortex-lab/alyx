#!/usr/bin/env python3

import os
import os.path as op
import sys
import json
import uuid
import re


if len(sys.argv) > 1 and sys.argv[1] == 'test':
    path = '../../data/all_dumped_anon.json'
    out = '../../data/all_dumped_anon.uuid.json'
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
            if not isinstance(value, int):
                continue
            new_pk = user_keys[value]
            item['fields'][field] = new_pk
            assert isinstance(item['fields'][field], str)
        elif field == 'users':
            value = item['fields'][field]
            item['fields'][field] = [user_keys.get(pk, pk) for pk in value]
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


# Hydrogel and water type
water = {
    'model': 'actions.watertype',
    'pk': '2127f637-0770-4639-8c22-3d73a94eecc3',
    'fields': {'name': 'Water', 'json': None}
}
hydrogel = {
    'model': 'actions.watertype',
    'pk': 'c68ed3b4-8a3d-47e2-a010-de7b9c027439',
    'fields': {'name': 'Hydrogel', 'json': None}
}
db.extend([water, hydrogel])

for item in db:
    if item['model'] == 'actions.wateradministration':
        if item['fields'].pop('hydrogel', None):
            item['fields']['water_type'] = hydrogel['pk']
        else:
            item['fields']['water_type'] = water['pk']


# sequences: line => allele
line_to_alleles = {
    '0aa6b854-9261-4b4f-b77b-6529ac83f1b9': {'0e6e433a-f495-44eb-b39c-2ae0971cbeef',
  '2ec63f31-2f9f-4da9-8181-1027a50bf2d2'},
 'cf771190-b55e-4920-ac44-5e79dc1a016e': {'4135407f-4535-4862-97e6-b21ab55a667b',
  'b839312c-6908-436b-9195-2ab639eac4fd'},
 '6a177a19-4787-461f-932b-a93cffe55f7c': {'0ff9cfbd-4e28-4319-87ef-67cdaa250c40',
  '4135407f-4535-4862-97e6-b21ab55a667b',
  '814ead25-6990-46be-96ea-bd56bb04166c',
  'b839312c-6908-436b-9195-2ab639eac4fd'},
 'cded6522-2c55-4e33-81d1-085436c7f511': {'2ec63f31-2f9f-4da9-8181-1027a50bf2d2'},
 '42b404ed-d20c-4457-aa4b-dce20d7d85d9': {'0ff9cfbd-4e28-4319-87ef-67cdaa250c40',
  '7554c30e-3e74-4476-8997-79a5636bf296'},
 'f902be83-7b4e-47e0-a789-a0cef85a7a79': {'20de452f-5a1c-47d6-b36a-0d432e836892',
  '43c64799-b59b-4b22-a01e-bdac9cfc61d7'},
 '94263b41-384f-46f2-9f56-f71cc9df91be': {'1879d9d2-cb7c-4fb0-b6de-5ee14a9fc5bb'},
 '48120ef8-7381-4b5e-b6c0-3dc9205f88d4': {'0e6e433a-f495-44eb-b39c-2ae0971cbeef',
  '0ff9cfbd-4e28-4319-87ef-67cdaa250c40',
  '814ead25-6990-46be-96ea-bd56bb04166c'},
 '9b059774-c7bf-4888-90d6-94155233da9d': {'0ff9cfbd-4e28-4319-87ef-67cdaa250c40',
  'b839312c-6908-436b-9195-2ab639eac4fd'},
 '920060f1-b55a-4e58-973c-5a7451d6df70': {'0e6e433a-f495-44eb-b39c-2ae0971cbeef',
  '0ff9cfbd-4e28-4319-87ef-67cdaa250c40'},
 '8359b881-8948-40b7-8dce-44ae27eb2497': {'20de452f-5a1c-47d6-b36a-0d432e836892',
  '7554c30e-3e74-4476-8997-79a5636bf296'},
 'a22a3316-8d09-462b-8dfb-c296a7a3c322': {'db8845d8-809a-40ef-b352-a38c3f13afab'},
 '1abeda95-9b48-480e-847b-4da11fbecfb1': {'7554c30e-3e74-4476-8997-79a5636bf296'},
 '80744e78-9297-4b58-a57a-c08a2fb2d059': {'b9b08320-b53d-4a3a-9591-a79433f13d2f'},
 '31031ec7-0516-45de-930b-cab33f37c321': {'3dec4319-be93-4d8b-b16f-c8222c603d55',
  '4135407f-4535-4862-97e6-b21ab55a667b'},
 '1632a84a-05d5-4128-9c06-2e29d8f5404b': {'47c625d9-76f4-4335-aa03-0601038288aa'},
 '2df44036-e54c-47cd-a43e-de53407d91a2': {'42a32fea-a17b-49a6-ba29-44fbac7fd849'},
 '5aca8c93-d7cb-4979-89a4-c6515cb014b2': {'20de452f-5a1c-47d6-b36a-0d432e836892',
  '43c64799-b59b-4b22-a01e-bdac9cfc61d7'},
 '0775ddf7-2622-4d8e-bc26-90f1b542d864': {'58063067-2a42-446a-a4bc-7fa2bd037484'},
 '2f50a372-8b22-49a1-aab3-d077a92fc233': {'8afc54ff-cefc-4184-8c9e-fb2d32b7bc50'},
 '50486c14-67b3-424a-8029-970fb482770c': {'0e6e433a-f495-44eb-b39c-2ae0971cbeef',
  '20de452f-5a1c-47d6-b36a-0d432e836892'},
 '15944d06-9066-4341-8cd9-c050f26f151f': {'55cd9bbf-6736-419b-be96-36e3723def9d',
  'db8845d8-809a-40ef-b352-a38c3f13afab'},
 '729192b9-b505-426b-9b55-ba712a902d03': {'0e6e433a-f495-44eb-b39c-2ae0971cbeef',
  '8afc54ff-cefc-4184-8c9e-fb2d32b7bc50'},
 '14d5d7f8-3794-4a91-a73b-f1cfa8764ddd': {'dd962692-d2fa-4486-a926-510a91996e2a'},
 '012bc9c2-a805-424b-bd61-80c764574786': {'0ff9cfbd-4e28-4319-87ef-67cdaa250c40',
  '43c64799-b59b-4b22-a01e-bdac9cfc61d7',
  'b839312c-6908-436b-9195-2ab639eac4fd'},
 'f648102e-9308-4b2a-8ee9-cf6f4e5b4874': {'b839312c-6908-436b-9195-2ab639eac4fd'},
 '689bd1a8-3256-48a3-b1ba-6da5710c7f35': {'43c64799-b59b-4b22-a01e-bdac9cfc61d7'},
 'e8c66ecf-6693-442f-9999-46816457890b': {'8afc54ff-cefc-4184-8c9e-fb2d32b7bc50'},
 '6fc8ff15-493e-45c1-8c1d-7642cf26bc20': {'0e6e433a-f495-44eb-b39c-2ae0971cbeef',
  '2ec63f31-2f9f-4da9-8181-1027a50bf2d2'},
 '99e6971c-0a3c-4a16-b9cf-3d0b02041ad4': {'2ec63f31-2f9f-4da9-8181-1027a50bf2d2'},
 'ae0dd798-89d7-4c3f-aa90-d3a317dd8789': {'8afc54ff-cefc-4184-8c9e-fb2d32b7bc50',
  'dd962692-d2fa-4486-a926-510a91996e2a'},
 '52fa8b8e-8b43-4fbf-af80-223de2874bf6': {'e4f5be9c-1df4-4495-9d44-821fc433016a'},
 '57077617-2a58-4472-b494-cdc7756590c8': {'6854013c-76b4-47be-ace2-3ae7cf6f8946'}}


line_to_sequences = {}
for item in db:
    if item['model'] == 'subjects.line':
        line_to_sequences[item['pk']] = item['fields'].pop('sequences', [])
        item['fields']['alleles'] = list(line_to_alleles.get(item['pk'], []))


# Set allele.sequences
for item in db:
    if item['model'] == 'subjects.allele':
        # Search the line.
        for line, alleles in line_to_alleles.items():
            if item['pk'] in alleles:
                item['fields']['sequences'] = line_to_sequences.get(line, [])
                break


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


# Moved modules.
for item in db:
    if item['model'] == 'equipment.lablocation':
        item['model'] = 'misc.lablocation'
    item['fields'].pop('weighing_scale', None)
    item['fields'].pop('brain_location', None)
    item['fields'].pop('timescale', None)


# Renames.
"""
Species.binomial_name => name
Litter.descriptive_name ==> name
Strain.descriptive_name => name
Sequence.informal_name => name
Allele.standard_name => name

Species.display_name => nickname
Line.auto_name => nickname
Allele.informal_name => nickname
"""
renames = [
    ('subjects.species', 'binomial', 'name'),
    ('subjects.litter', 'descriptive_name', 'name'),
    ('subjects.strain', 'descriptive_name', 'name'),
    ('subjects.sequence', 'informal_name', 'name'),
    ('subjects.allele', 'standard_name', 'name'),
    ('subjects.species', 'display_name', 'nickname'),
    ('subjects.line', 'auto_name', 'nickname'),
    ('subjects.allele', 'informal_name', 'nickname'),
    ('data.datarepository', 'dns', 'hostname'),
]

for item in db:
    for model, old, new in renames:
        if item['model'] == model and old in item['fields']:
            item['fields'][new] = item['fields'].pop(old)


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


# Replace lamis_cage by cage
with open(out, 'r') as f:
    contents = f.read().replace('lamis_cage', 'cage')
with open(out, 'w') as f:
    f.write(contents)


'''
with open('user_keys.json', 'w') as f:
    json.dump(user_keys, f, indent=1)
'''
