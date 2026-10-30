"""One-time helper for databases made before the fixed department list.

    python manage.py upgrade_departments

Renames the common old department names to the official ones everywhere (students, teachers, exams, assignments,
study material, attendance) and lists anything it could not match, so you can fix those in Admin > Students / Teachers.
Semesters of old records are 1: update them from Admin > Students (pencil icon)."""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.departments import DEPARTMENTS
from apps.accounts.models import StudentProfile, TeacherProfile
from apps.assignments.models import Assignment
from apps.attendance.models import Attendance
from apps.exams.models import Exam
from apps.materials.models import StudyMaterial

ALIASES = {
    'computer science engineering': 'Computer Science and Engineering (CSE)',
    'computer science and engineering': 'Computer Science and Engineering (CSE)',
    'cse': 'Computer Science and Engineering (CSE)',
    'information technology': 'Information Technology (IT)',
    'it': 'Information Technology (IT)',
    'electronics and communication engineering': 'Electronics & Communication Engineering (ECE)',
    'ece': 'Electronics & Communication Engineering (ECE)',
    'biotechnology': 'Bio Technology',
    'bio technology': 'Bio Technology',
    'mca': 'Master of Computer Applications (MCA)',
    'mba': 'Master of Business Administration (MBA)',
    'applied science and humanities': 'Applied Science & Humanities',
    'electrical engineering': 'Electrical Engineering',
    'mechanical engineering': 'Mechanical Engineering',
    'civil engineering': 'Civil Engineering',
    'chemical engineering': 'Chemical Engineering',
    'agricultural engineering': 'Agricultural Engineering',
    'agriculture': 'Agricultural Engineering',
    'food technology': 'Food Technology',
}
MODELS = [StudentProfile, TeacherProfile, Exam, Assignment, StudyMaterial, Attendance]


class Command(BaseCommand):
    help = 'Rename old department names to the official list.'

    @transaction.atomic
    def handle(self, *args, **opts):
        changed, unknown = 0, {}
        for model in MODELS:
            for old in model.objects.exclude(department='').values_list('department', flat=True).distinct():
                if old in DEPARTMENTS:
                    continue
                new = ALIASES.get(' '.join(old.lower().split()))
                if new:
                    changed += model.objects.filter(department=old).update(department=new)
                else:
                    unknown.setdefault(old, 0)
                    unknown[old] += model.objects.filter(department=old).count()
        self.stdout.write(self.style.SUCCESS(f'{changed} record(s) renamed.'))
        for name, n in unknown.items():
            self.stdout.write(self.style.WARNING(f'Not matched: "{name}" ({n} record(s)). Fix it in Admin > Students or Teachers.'))
