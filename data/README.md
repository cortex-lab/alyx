This directory should contain:

* `dumped_static.json` obtained with:

    ```
    python3 /data/www/alyx/alyx/manage.py dumpdata auth.user subjects.species subjects.strain subjects.allele subjects.line subjects.linegenotypetest subjects.source subjects.sequence equipment.lablocation actions.proceduretype --indent 2 --exclude auth.permission --exclude contenttypes > /data/nick/alyx-test/dumphere/dumped_static.json
    ```

* `gdrive.json` obtained as [explained here](http://gspread.readthedocs.io/en/latest/oauth2.html).
