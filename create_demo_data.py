"""Kept for backwards compatibility: same as `python manage.py seed_demo --reset`."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.core.management import call_command

call_command('seed_demo', reset=True)
