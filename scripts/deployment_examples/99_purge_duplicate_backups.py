#!/usr/bin/env python3

import os
import shlex
import re
from subprocess import Popen, PIPE
from datetime import datetime
from dateutil.parser import isoparse

r = re.compile(r'2[0-9]{3}\-[0-9]{2}\-[0-9]{2}')

#host = "flatiron"  # for local testing
host = "alyx@ibl.flatironinstitute.org"

cmd = "ssh -q -p 61022 -t {host} 'ls -s1 /mnt/ibl/json/*.sql.gz'".format(host=host)

p = Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE)
files_flatiron = [tuple(_.decode('utf-8').strip().split(' ')) for _ in p.stdout.readlines()]
files_flatiron = {v.replace('/mnt/ibl/json/', '').replace('alyxfull', 'alyx_full'): int(k) for k, v in files_flatiron}

p = Popen("ls -s1 /mnt/xvdf/alyx-backups/2*/*.sql.gz", shell=True, stdout=PIPE, stderr=PIPE)
files_aws = [tuple(_.decode('utf-8').strip().split(' ')) for _ in p.stdout.readlines()]
files_aws = {v.replace('/mnt/xvdf/alyx-backups/', '').replace('/', '_'): int(k) for k, v in files_aws}

for fn in sorted(files_aws):
    if fn in sorted(files_flatiron):
        ds = r.search(fn).group(0)
        d = isoparse(ds)
        # Only delete duplicate backups older than 7 days and not those on the first of a month.
        if (datetime.now() - d).days >= 7 and abs(files_aws[fn] - files_flatiron[fn]) <= 4 and d.day != 1:
            path = '/mnt/xvdf/alyx-backups/%s/alyx_full.sql.gz' % ds
            print("Delete %s on the EC2 instance as it already exists on flatiron" % path)
