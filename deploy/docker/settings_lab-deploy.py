import os
from textwrap import dedent

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/London'
GLOBUS_CLIENT_ID = os.getenv('GLOBUS_CLIENT_ID')
SUBJECT_REQUEST_EMAIL_FROM = 'alyx@internationalbrainlab.org'
DEFAULT_SOURCE = 'IBL'
DEFAULT_PROTOCOL = '1'
SUPERUSERS = ('root',)
STOCK_MANAGERS = ('root',)
WEIGHT_THRESHOLD = 0.75
DEFAULT_LAB_NAME = 'cortexlab'
WATER_RESTRICTIONS_EDITABLE = False  # if set to True, all users can edit water restrictions
DEFAULT_LAB_PK = '4027da48-7be3-43ec-a222-f75dffe36872'
SESSION_REPO_URL = \
    "http://ibl.flatironinstitute.org/{lab}/Subjects/{subject}/{date}/{number:03d}/"
NARRATIVE_TEMPLATES = {
    'Headplate implant': dedent('''
    == General ==

    Start time (hh:mm):   ___:___
    End time (hh:mm):    ___:___

    Bregma-Lambda :   _______  (mm)

    == Drugs == (copy paste as many times as needed; select IV, SC or IP)
    __________________( IV / SC / IP ) Admin. time (hh:mm)  ___:___

    == Coordinates ==  (copy paste as many times as needed; select B or L)
    (B / L) - Region: AP:  _______  ML:  ______  (mm)
    Region: _____________________________

    == Notes ==
    <write your notes here>
        '''),
}
