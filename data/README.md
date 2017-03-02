This directory should contain:

* `dumped_static.json` obtained with:

    ```
    python3 /data/www/alyx/alyx/manage.py dumpdata auth.user auth.group subjects.species subjects.strain subjects.allele subjects.line subjects.linegenotypetest subjects.source subjects.sequence equipment.lablocation actions.proceduretype --indent 2 --natural-foreign -e sessions -e admin > dumped_static.json
    ```

    Note: at the moment, you have to manually delete the permissions of Experiment or Charu in the json before importing, otherwise you'll enter into some bug. These users are set as superusers manually.

* `gdrive.json` obtained as [explained here](http://gspread.readthedocs.io/en/latest/oauth2.html).

Then, to import the data:

* `make reset_all`: this will **completely erase the alyx database** and recreate it from the dumped data in the json file, and from the google sheets.
