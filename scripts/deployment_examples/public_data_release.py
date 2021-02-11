"""
DATA RELEASE PROTOTYPE
From a full database, prune only the sessions needed for a public data release
At the end, generates commands to be run on the flatiron server
"""

from django.conf import settings

from actions.models import Session
from subjects.models import Subject
from misc.models import LabMember
from data.models import DataRepository
eids = ['89f0d6ff-69f4-45bc-b89e-72868abb042a',
        'd33baf74-263c-4b37-a0d0-b79dcb80a764']

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Makes sure this is not run on a production database
# THE CODE BELOW WILL PERMANENTLY DELETE ALL SESSIONS NOT IN THE EIDS LIST ABOVE
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
assert 'public.alyx.internationalbrainlab.org' in settings.ALLOWED_HOSTS


# first prune the database
# have to delete sessions batch by batch to avoid out of memory issues
N = 500
while True:
    other_sessions = Session.objects.exclude(pk__in=eids)
    print(other_sessions.count())
    if other_sessions.count() > N:
        to_del = Session.objects.filter(pk__in=other_sessions[:N].values_list('pk'))
        to_del.delete()
    else:
        other_sessions.delete()
        break

ses = Session.objects.all()

Subject.objects.exclude(pk__in=ses.values_list('subject')).delete()
LabMember.objects.exclude(pk__in=ses.values_list('users').distinct()).delete()
DataRepository.objects.filter(globus_is_personal=True).delete()

repos = DataRepository.objects.all()
for repo in repos:
     repo.data_url = repo.data_url.replace("http://ibl.flatironinstitute.org/",
                                           "http://ibl.flatironinstitute.org/public/")
     repo.save()


LabMember.objects.create_user('iblpublic', password="NeuroPhysTest")

# Then create the commands to be run on the flatiron server
# (TODO run commands from here but needs SSH keypairs)
from pathlib import Path
ROOT_PATH = Path('/mnt/ibl')
PUBLIC_PATH = Path('/mnt/ibl/public')
for s in ses:
    rel_session_path = Path(s.lab.name, 'Subjects', s.subject.nickname,
                            s.start_time.strftime("%Y-%m-%d"), str(s.number).zfill(3))
    cmd0 = f"mkdir -p {PUBLIC_PATH.joinpath(rel_session_path).parent}"
    cmd1 = f"ln -s {ROOT_PATH.joinpath(rel_session_path)} {PUBLIC_PATH.joinpath(rel_session_path)}"
    print(cmd0)
    print(cmd1)
