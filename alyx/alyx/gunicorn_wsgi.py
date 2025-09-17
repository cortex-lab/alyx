"""
WSGI config for alyx project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
from pathlib import Path

from whitenoise import WhiteNoise
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyx.settings")
application = get_wsgi_application()
application = WhiteNoise(application, root=str(Path(__file__).parents[1].joinpath('static')))
