import json
import logging
import os
import os.path as op
import re
from pathlib import Path

from django.db.models import Case, When, Count, Q

from alyx import settings
from data.models import FileRecord, Dataset, DatasetType, DataFormat, DataRepository
from actions.models import Session

from ibllib.io. globus import Globus

logger = logging.getLogger(__name__)


RELATIVE_PATH_TEMPLATE = '{lab}/Subjects/{subject}/{date}/{number:03d}/'


# def is_on_flatiron(session_eid, filename=None, filesize=None):
#     qs = Dataset.objects.filter(session=session_eid, file_records__data_repository__globus_is_personal=False)
#     if size is not None:
#         qs = qs.filter(file_size=size)
#     return len(qs) > 0


def _add_uuid_to_filename(fn, uuid):
    dpath, ext = op.splitext(fn)
    return dpath + '.' + str(uuid) + ext


def get_session_root_path(session_eid):
    session = Session.objects.get(pk=session_eid)
    subject = session.subject
    return Path(RELATIVE_PATH_TEMPLATE.format(
        lab=subject.lab,
        subject=subject.nickname,
        date=session.start_time.strftime('%Y-%m-%d'),
        number=session.number or 1,
    ))


def exist_on_flatiron(session_eid, filenames, sizes=None):
    """Return whether specified session files exist on Flatiron."""
    # filenames are relative to the session root, eg alf/spikes.times.npy
    if isinstance(filenames, str):
        raise ValueError("Please specify a list of files")
    root = get_session_root_path(session_eid)
    relative_paths = [root / filename for filename in filenames]
    # check on flatiron via globus that the given files exist or not
    g = Globus()
    return g.files_exist('flatiron', relative_paths, sizes=sizes, remove_uuid=True)


def datasets_not_on_flatiron(session_eid=None):
    # return all datasets missing on flatiron, according to their exists field
    pass


def upload_missing_files(session_eid=None):
    # get all datasets missing on flatiron, according to their exists field
    # launch an upload, warn if files do not exist anywhere, and wait
    # check that all files exist, and update the exists field accordingly
    pass
