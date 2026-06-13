#!/usr/bin/env python3
"""Django's command-line utility for the atn corpus-atlas web app."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "atlas.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is it installed? (pip install django)"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
