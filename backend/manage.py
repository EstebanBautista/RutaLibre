#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Local convenience: read .env.local (pulled from Vercel/Neon) and .env.
    # Hosted environments have no such files and use real environment variables.
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv('.env.local')
        load_dotenv('.env')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
