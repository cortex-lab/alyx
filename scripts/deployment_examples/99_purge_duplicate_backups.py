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
FLAT_IRON_DIR = "/mnt/ibl/json"
LOCAL_DIR = "/backups/alyx-backups"
CMD = f"ssh -i /home/ubuntu/.ssh/sdsc_alyx.pem -q -p 62022 -t {HOST} 'ls -s1 {FLAT_IRON_DIR}/*.sql.gz'"
KEEP_DAYS = 2

parser = argparse.ArgumentParser(description='Removes local backup files if they exist on the flatiron remote server')
parser.add_argument('--dry', dest='dry', help='Dry Run', required=False, action='store_true')
args = parser.parse_args()
dry = args.dry

r = re.compile(r'2[0-9]{3}\-[0-9]{2}\-[0-9]{2}')

# Get all SQL backup files currently on flatiron
p = Popen(shlex.split(CMD), stdout=PIPE, stderr=PIPE)
files_flatiron = [tuple(_.decode('utf-8').strip().split(' ')) for _ in p.stdout.readlines()]
files_flatiron = {v.replace(str(FLAT_IRON_DIR) + '/', '').replace('alyxfull', 'alyx_full'): int(k) for k, v in files_flatiron}

# Get all SQL backup files currently on the server
p = Popen(f"ls -s1 {Path(LOCAL_DIR).joinpath('2*/alyx_full.*.gz')}", shell=True, stdout=PIPE, stderr=PIPE)
files_aws = [tuple(_.decode('utf-8').strip().split(' ')) for _ in p.stdout.readlines()]
files_aws = {v.replace(str(LOCAL_DIR) + '/', '').replace('/', '_'): int(k) for k, v in files_aws}

# Find all backups locally that are also on flatiron, with (almost) the same file size, older than
# 7 days, and not starting the first of a month.
for fn in sorted(files_aws):
    if fn in sorted(files_flatiron):
        ds = r.search(fn).group(0)
        d = isoparse(ds)
        if (datetime.now() - d).days >= KEEP_DAYS and abs(files_aws[fn] - files_flatiron[fn]) <= 12 and d.day != 1:
            sql_file = Path(LOCAL_DIR).joinpath('%s/alyx_full.sql.gz' % ds)
            json_file = Path(LOCAL_DIR).joinpath('%s/alyx_full.json.gz' % ds)
            if sql_file.exists():
                print("Delete %s on the EC2 instance as it already exists on flatiron" % sql_file)
                if not dry:
                    sql_file.unlink()
            if json_file.exists():
                print("Delete %s on the EC2 instance as it already exists on flatiron" % json_file)
                if not dry:
                    json_file.unlink()
