#!/usr/bin/env python3
import argparse
from pathlib import Path
import shlex
import re
from subprocess import Popen, PIPE
from datetime import datetime
from dateutil.parser import isoparse

# HOST = "flatiron"  # for local testing
HOST = "alyx@ibl.flatironinstitute.org"
CMD = "ssh -q -p 61022 -t {host} 'ls -s1 /mnt/ibl/json/*.sql.gz'".format(host=HOST)
KEEP_DAYS = 7

parser = argparse.ArgumentParser(description='Removes local backup files if they exist on the flatiron remote server')
parser.add_argument('--dry', dest='dry', help='Dry Run', required=False, action='store_true')
args = parser.parse_args()
dry = args.dry

r = re.compile(r'2[0-9]{3}\-[0-9]{2}\-[0-9]{2}')

# Get all SQL backup files currently on flatiron
p = Popen(shlex.split(CMD), stdout=PIPE, stderr=PIPE)
files_flatiron = [tuple(_.decode('utf-8').strip().split(' ')) for _ in p.stdout.readlines()]
files_flatiron = {v.replace('/mnt/ibl/json/', '').replace('alyxfull', 'alyx_full'): int(k) for k, v in files_flatiron}

# Get all SQL backup files currently on the server
p = Popen("ls -s1 /mnt/xvdf/alyx-backups/2*/alyx_full.*.gz", shell=True, stdout=PIPE, stderr=PIPE)
files_aws = [tuple(_.decode('utf-8').strip().split(' ')) for _ in p.stdout.readlines()]
files_aws = {v.replace('/mnt/xvdf/alyx-backups/', '').replace('/', '_'): int(k) for k, v in files_aws}

# Find all backups locally that are also on flatiron, with (almost) the same file size, older than
# 7 days, and not starting the first of a month.
for fn in sorted(files_aws):
    if fn in sorted(files_flatiron):
        ds = r.search(fn).group(0)
        d = isoparse(ds)
        if (datetime.now() - d).days >= KEEP_DAYS and abs(files_aws[fn] - files_flatiron[fn]) <= 4 and d.day != 1:
            sql_file = Path('/mnt/xvdf/alyx-backups/%s/alyx_full.sql.gz' % ds)
            json_file = Path('/mnt/xvdf/alyx-backups/%s/alyx_full.json.gz' % ds)
            if sql_file.exists():
                print("Delete %s on the EC2 instance as it already exists on flatiron" % sql_file)
                if not dry:
                    sql_file.unlink()
            if json_file.exists():
                print("Delete %s on the EC2 instance as it already exists on flatiron" % json_file)
                if not dry:
                    json_file.unlink()
