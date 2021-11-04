#!/usr/bin/env python3
import os
import sys

if __name__ == "__main__":
    if 'GITHUB_ACTIONS' in os.environ:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyx.settings_template")
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyx.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
