"""Creates demo accounts, exams, results, assignments, attendance and notifications.

    python manage.py seed_demo           # first time
    python manage.py seed_demo --reset   # wipe everything and start again

No emails are sent while seeding.
"""
import io
import random
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, StudentProfile, TeacherProfile
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.attendance.models import Attendance
from apps.exams.models import Exam, Question, ExamSubmission, StudentAnswer
from apps.exams.utils import refresh_exam_totals
from apps.materials.models import StudyMaterial
from apps.notifications.models import Notification
from apps.performance.models import PerformanceReport
from apps.reattempt.models import ReattemptRequest
from ai_engine.evaluation.score_generator import generate_scores
from ai_engine.performance.recommendation import generate_recommendations
from ai_engine.performance.weak_topic_detector import detect_weak_topics

CSE, ME = 'Computer Science and Engineering (CSE)', 'Mechanical Engineering'
MCA = 'Master of Computer Applications (MCA)'

STUDENTS = [  # username, first, last, department, semester, roll, skill (chance of a right answer)
    ('student1', 'Aarav', 'Sharma', CSE, 3, 'CSE301', 0.55),
    ('student2', 'Diya', 'Patel', CSE, 3, 'CSE302', 0.92),
    ('student3', 'Rohan', 'Das', CSE, 3, 'CSE303', 0.80),
    ('student4', 'Ananya', 'Roy', CSE, 3, 'CSE304', 0.45),
    ('student5', 'Kabir', 'Singh', CSE, 3, 'CSE305', 0.70),
    ('student6', 'Meera', 'Nair', CSE, 3, 'CSE306', 0.88),
    ('student7', 'Ishaan', 'Gupta', CSE, 3, 'CSE307', 0.35),
    ('student8', 'Sara', 'Khan', CSE, 3, 'CSE308', 0.65),
    ('student9', 'Vihaan', 'Joshi', ME, 2, 'ME201', 0.75),
    ('student10', 'Tara', 'Mehta', ME, 2, 'ME202', 0.60),
    ('student11', 'Nikhil', 'Rao', MCA, 2, 'MCA201', 0.70),     # MCA has 4 semesters
    ('student12', 'Pooja', 'Iyer', CSE, 4, 'CSE401', 0.82),     # same department, next semester: sees none of the semester 3 work
]

MATH_QS = [  # topic, text, options, correct
    ('Algebra', 'Solve for x: 2x + 6 = 14', ['2', '4', '6', '8'], 'B'),
    ('Algebra', 'What is the value of (a + b)^2 when a = 2 and b = 3?', ['13', '20', '25', '36'], 'C'),
    ('Algebra', 'Factorise x^2 - 9', ['(x-3)(x-3)', '(x+3)(x+3)', '(x-3)(x+3)', 'x(x-9)'], 'C'),
    ('Geometry', 'The sum of the angles in a triangle is', ['90 degrees', '180 degrees', '270 degrees', '360 degrees'], 'B'),
    ('Geometry', 'Area of a circle with radius 7 (pi = 22/7)', ['44', '154', '308', '49'], 'B'),
    ('Calculus', 'The derivative of x^2 is', ['x', '2x', 'x^2', '2'], 'B'),
    ('Calculus', 'The derivative of a constant is', ['0', '1', 'the constant', 'undefined'], 'A'),
    ('Matrices', 'The order of a matrix with 3 rows and 2 columns is', ['2 x 3', '3 x 2', '3 x 3', '6'], 'B'),
    ('Matrices', 'The determinant of the identity matrix of order 2 is', ['0', '1', '2', '-1'], 'B'),
    ('Matrices', 'If A is 2 x 3 and B is 3 x 4, then AB has order', ['2 x 4', '3 x 3', '4 x 2', 'cannot be found'], 'A'),
]
PHYSICS_QS = [
    ('Mechanics', 'The SI unit of force is the', ['Joule', 'Newton', 'Watt', 'Pascal'], 'B'),
    ('Mechanics', 'Acceleration is the rate of change of', ['distance', 'mass', 'velocity', 'force'], 'C'),
    ('Electricity', 'Ohm\'s law states that V equals', ['I / R', 'I x R', 'R / I', 'I + R'], 'B'),
    ('Electricity', 'The unit of electrical resistance is the', ['Ampere', 'Volt', 'Ohm', 'Coulomb'], 'C'),
]

SUBJECTIVE = {
    'Algebra': ('Explain what algebra is in your own words.',
                'Algebra is a branch of mathematics that uses symbols and variables to write an equation and solve for unknown values.',
                'symbols, mathematics, equation, variable',
                ['Algebra is a branch of mathematics that uses symbols and a variable to form an equation and find unknown values.',
                 'It uses letters like x for numbers in an equation.',
                 'I do not remember this one.']),
    'Mechanics': ('Explain Newton\'s second law of motion.',
                  'Newton\'s second law says that the force on an object equals its mass multiplied by its acceleration.',
                  'force, mass, acceleration',
                  ['The force on an object equals its mass multiplied by its acceleration, so a bigger force gives a bigger acceleration.',
                   'Force depends on mass.',
                   'Objects like to keep moving.']),
}

TEACHERS = [
    ('teacher1', 'Priya', 'Banerjee', 'T001', 'Mathematics', CSE),
    ('teacher2', 'Arjun', 'Mukherjee', 'T002', 'Physics', ME),
]


def tiny_pdf(title, lines):
    """Builds a small, valid one-page PDF so demo files open in any viewer."""
    esc = lambda t: t.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    text = 'BT /F1 20 Tf 60 760 Td (%s) Tj /F1 12 Tf 0 -34 Td 16 TL\n' % esc(title)
    text += ''.join('(%s) Tj T*\n' % esc(l) for l in lines) + 'ET'
    objs = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
            '<< /Length %d >>\nstream\n%s\nendstream' % (len(text), text), '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    out, offsets = '%PDF-1.4\n', []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out)); out += '%d 0 obj\n%s\nendobj\n' % (i, o)
    xref = len(out)
    out += 'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + ''.join('%010d 00000 n \n' % o for o in offsets)
    out += 'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (len(objs) + 1, xref)
    return out.encode('latin-1')


def tiny_png(text):
    """A small PNG 'photo' (used for demo proof and assignment photos)."""
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (480, 220), (244, 247, 252))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 471, 211], outline=(23, 32, 91), width=3)
    d.text((24, 40), text, fill=(23, 32, 91))
    d.text((24, 90), 'Demo image created by SmartEdu', fill=(74, 83, 133))
    buf = io.BytesIO(); img.save(buf, 'PNG')
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Create demo users, exams, results, assignments, attendance and notifications.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete all users and data first.')

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts['reset']:
            User.objects.all().delete()
            Exam.objects.all().delete()
            self.stdout.write('Old data removed.')
        elif User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('Demo data already exists. Run with --reset to rebuild it.'))
            return

        rng = random.Random(42)
        now = timezone.now()

        admin = User.objects.create_superuser('admin', 'admin@smartedu.local', 'admin123', role='ADMIN',
                                              first_name='Site', last_name='Admin', is_verified=True)
        teachers = {}
        for uname, fn, ln, emp, subj, dept in TEACHERS:
            u = User.objects.create_user(uname, f'{uname}@smartedu.local', 'teacher123', role='TEACHER',
                                         first_name=fn, last_name=ln, is_verified=True)
            TeacherProfile.objects.create(user=u, employee_id=emp, subject=subj, department=dept)
            teachers[uname] = u

        students = []
        for uname, fn, ln, dept, sem, roll, skill in STUDENTS:
            u = User.objects.create_user(uname, f'{uname}@smartedu.local', 'student123', role='STUDENT',
                                         first_name=fn, last_name=ln, is_verified=True)
            StudentProfile.objects.create(user=u, roll_number=roll, department=dept, semester=sem,
                                          guardian_name=f'Parent of {fn}', guardian_email=f'guardian.{uname}@example.com')
            u.skill = skill
            students.append(u)
        by_name = {s.username: s for s in students}
        t1, t2 = teachers['teacher1'], teachers['teacher2']

        def make_exam(title, subject, teacher, dept, sem, days_ago, minutes, qs, subjective_topic, closes_after_days=2, status='PUBLISHED'):
            opens = now - timedelta(days=days_ago)
            exam = Exam.objects.create(
                title=title, subject=subject, department=dept, semester=sem, duration_minutes=minutes,
                scheduled_at=opens, closes_at=opens + timedelta(days=closes_after_days), created_by=teacher, status=status,
                description=f'{subject} test for {dept}, semester {sem}.')
            for topic, text, opts_, correct in qs:
                Question.objects.create(exam=exam, qtype='MCQ', text=text, topic=topic, marks=5,
                                        option_a=opts_[0], option_b=opts_[1], option_c=opts_[2], option_d=opts_[3],
                                        correct_option=correct)
            if subjective_topic:
                text, ideal, kw, _ = SUBJECTIVE[subjective_topic]
                Question.objects.create(exam=exam, qtype='SUBJECTIVE', text=text, topic=subjective_topic, marks=10,
                                        ideal_answer=ideal, keywords=kw)
            refresh_exam_totals(exam)
            if status == 'PUBLISHED':
                Notification.objects.bulk_create([
                    Notification(recipient=s, sender=teacher, title=f'New exam: {title}', ntype='EXAM', related_exam=exam,
                                 message=f'{subject} exam. Duration {minutes} minutes.')
                    for s in students if (s.student_profile.department, s.student_profile.semester) == (dept, sem)])
            return exam

        def take(exam, student, when):
            sub = ExamSubmission.objects.create(exam=exam, student=student)
            ExamSubmission.objects.filter(id=sub.id).update(
                started_at=when, submitted_at=when + timedelta(minutes=exam.duration_minutes - 5), is_completed=True)
            sub.refresh_from_db()
            for q in exam.questions.all():
                a = StudentAnswer(submission=sub, question=q)
                if q.qtype == 'MCQ':
                    a.selected_option = q.correct_option if rng.random() < student.skill else rng.choice([c for c in 'ABCD' if c != q.correct_option])
                else:
                    answers = SUBJECTIVE[q.topic][3]
                    r = rng.random()
                    a.subjective_text = answers[0] if r < student.skill - 0.1 else answers[1] if r < student.skill + 0.25 else answers[2]
                a.save()
            generate_scores(sub)
            detect_weak_topics(student, sub)
            PerformanceReport.objects.filter(student=student, exam=exam).update(generated_at=when)
            return sub

        cse = [s for s in students if (s.student_profile.department, s.student_profile.semester) == (CSE, 3)]
        me = [s for s in students if (s.student_profile.department, s.student_profile.semester) == (ME, 2)]

        e1 = make_exam('Algebra and Geometry Test', 'Mathematics', t1, CSE, 3, 21, 40, MATH_QS[:5], 'Algebra')
        e2 = make_exam('Calculus Quick Quiz', 'Mathematics', t1, CSE, 3, 14, 20, MATH_QS[3:7], None)
        for s in cse:
            take(e1, s, now - timedelta(days=21, hours=-1))
            if s.username != 'student7':
                take(e2, s, now - timedelta(days=14, hours=-1))

        e5 = make_exam('Unit Test: Basic Algebra', 'Mathematics', t1, ME, 2, 12, 30, MATH_QS[:3], None)
        for s in me:
            take(e5, s, now - timedelta(days=12, hours=-1))

        # A closed exam that some students missed, with the three possible outcomes of a re-attempt request
        e6 = make_exam('Matrices Mid-term Quiz', 'Mathematics', t1, CSE, 3, 8, 20, MATH_QS[7:], None, closes_after_days=3)
        for s in cse:
            if s.username not in ('student1', 'student4', 'student7', 'student8'):   # student8 missed it and has not asked yet
                take(e6, s, now - timedelta(days=8, hours=-2))
        ReattemptRequest.objects.create(
            exam=e6, student=by_name['student1'], status='PENDING',
            reason='I had a high fever and was advised bed rest by my doctor on the day of the quiz. The medical certificate is attached.',
            proof=ContentFile(tiny_pdf('Medical certificate (demo)', ['Patient: Aarav Sharma', 'Advised rest for 3 days.']), name='medical-certificate.pdf'))
        ReattemptRequest.objects.create(
            exam=e6, student=by_name['student4'], status='APPROVED', decided_by=t1, decided_at=now - timedelta(hours=5),
            extended_until=now + timedelta(days=2), teacher_comment='Approved. Please attempt it within two days.',
            reason='My village had a power and internet failure all day, so I could not log in before the quiz closed. A letter from the panchayat is attached.',
            proof=ContentFile(tiny_png('Letter: internet outage (demo)'), name='outage-letter.png'))
        ReattemptRequest.objects.create(
            exam=e6, student=by_name['student7'], status='REJECTED', decided_by=t1, decided_at=now - timedelta(days=1),
            teacher_comment='The proof does not cover the exam date.',
            reason='I forgot the date of the quiz and only remembered after it closed, sorry.',
            proof=ContentFile(tiny_png('Note (demo)'), name='note.png'))
        Notification.objects.create(recipient=t1, sender=by_name['student1'], ntype='REATTEMPT', title=f'Re-attempt request: {e6.title}',
                                    message='Aarav Sharma missed the exam and sent a reason with proof.')
        Notification.objects.create(recipient=by_name['student4'], sender=t1, ntype='REATTEMPT', title=f'Re-attempt approved: {e6.title}',
                                    message='Your teacher gave you another chance. Take it within two days.')

        # A live exam, an upcoming exam and a draft
        make_exam('Physics Basics Quiz', 'Physics', t2, CSE, 3, 0.1, 25, PHYSICS_QS, 'Mechanics')
        make_exam('Chapter Test: Algebra Revision', 'Mathematics', t1, CSE, 3, -2, 30, MATH_QS[:3], 'Algebra', closes_after_days=1)
        make_exam('Draft: Trigonometry', 'Mathematics', t1, CSE, 3, -5, 30, MATH_QS[:2], None, status='DRAFT')

        # Assignments: topics only; students upload work; the teacher rates it
        def assign(title, subject, teacher, dept, sem, due_days, desc=''):
            a = Assignment.objects.create(title=title, subject=subject, department=dept, semester=sem, created_by=teacher, description=desc,
                                          due_date=now + timedelta(days=due_days))
            Notification.objects.bulk_create([
                Notification(recipient=s, sender=teacher, ntype='ASSIGNMENT', title=f'New assignment: {title}', message=f'{subject}.')
                for s in students if (s.student_profile.department, s.student_profile.semester) == (dept, sem)])
            return a

        def submit(a, student, days_ago, review=True, as_photo=False):
            when = now - timedelta(days=days_ago)
            data = tiny_png(f'{student.first_name}: {a.title}') if as_photo else tiny_pdf(a.title, [f'Submitted by {student.get_full_name()}'])
            name = 'my-work.png' if as_photo else 'my-assignment.pdf'
            sub = AssignmentSubmission.objects.create(
                assignment=a, student=student, file=ContentFile(data, name=name), submitted_at=when,
                note='Please check my solved examples.' if rng.random() < .4 else '')
            if review:
                rating = max(1, min(5, round(student.skill * 5 + rng.uniform(-0.8, 0.8))))
                sub.rating, sub.reviewed_by, sub.reviewed_at = rating, a.created_by, when + timedelta(days=1)
                sub.review = {5: 'Excellent, clear and complete.', 4: 'Very good. Add a few more examples.', 3: 'Fair. Show more steps.',
                              2: 'Needs more effort and detail.', 1: 'Incomplete. Please see me.'}[rating]
                sub.save()
            return sub

        a1 = assign('Matrix operations: solved examples', 'Mathematics', t1, CSE, 3, -10, 'Solve five problems on matrix addition and multiplication.')
        for s in cse:
            if s.username != 'student7':
                submit(a1, s, 11, as_photo=(s.username in ('student5', 'student8')))
        a2 = assign('Newton\'s laws: short summary', 'Physics', t2, CSE, 3, -4)
        for s in cse:
            if rng.random() < .8:
                submit(a2, s, 5)
        a3 = assign('Linear equations worksheet', 'Mathematics', t1, CSE, 3, 3)
        submit(a3, by_name['student2'], 1, review=False)
        submit(a3, by_name['student6'], 0, review=False, as_photo=True)
        a4 = assign('Stress and strain: reading notes', 'Physics', t2, ME, 2, 6)
        submit(a4, by_name['student9'], 0, review=False)

        # Study material: two real files and two links
        for title, subj, dept, sem, teacher, fname, data, desc in [
            ('Algebra formula sheet', 'Mathematics', CSE, 3, t1, 'algebra-formulas.pdf',
             tiny_pdf('Algebra formula sheet', ['(a + b)^2 = a^2 + 2ab + b^2', '(a - b)^2 = a^2 - 2ab + b^2', 'a^2 - b^2 = (a - b)(a + b)']),
             'Keep this handy while revising for the algebra test.'),
            ('Newton\'s laws notes', 'Physics', CSE, 3, t2, 'newton-notes.pdf',
             tiny_pdf('Newton\'s laws notes', ['First law: inertia', 'Second law: F = m a', 'Third law: action and reaction']),
             'Read before the Physics Basics Quiz.'),
        ]:
            StudyMaterial.objects.create(title=title, subject=subj, department=dept, semester=sem, uploaded_by=teacher, description=desc,
                                         file=ContentFile(data, name=fname))
        StudyMaterial.objects.create(title='Khan Academy: Derivatives intro', subject='Mathematics', department=CSE, semester=3, uploaded_by=t1,
                                     link='https://www.khanacademy.org/math/calculus-1', description='Video lessons that go with the calculus quiz.')
        StudyMaterial.objects.create(title='Basic algebra practice', subject='Mathematics', department=ME, semester=2, uploaded_by=t1,
                                     link='https://www.khanacademy.org/math/algebra', description='Extra practice for the algebra unit test.')

        # Attendance for the last 3 weeks (weekdays only)
        records = []
        for offset in range(0, 21):
            day = (now - timedelta(days=offset)).date()
            if day.weekday() >= 5:
                continue
            for s in students:
                chance = rng.random()
                low = s.username in ('student4', 'student7')
                status = 'ABSENT' if chance < (0.28 if low else 0.07) else 'LATE' if chance < (0.38 if low else 0.14) else 'PRESENT'
                records.append(Attendance(student=s, date=day, status=status, department=s.student_profile.department,
                                          semester=s.student_profile.semester,
                                          marked_by=t1 if s.student_profile.department == CSE else t2))
        Attendance.objects.bulk_create(records)

        for s in students:
            generate_recommendations(s)
        Notification.objects.create(recipient=students[0], sender=admin, title='Welcome to SmartEdu',
                                    message='Your account is ready. Check your exams, assignments, attendance and weak topics from the menu.',
                                    ntype='GENERAL')

        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
        self.stdout.write('  admin    / admin123')
        self.stdout.write('  teacher1 / teacher123   (Mathematics, CSE department)')
        self.stdout.write('  teacher2 / teacher123   (Physics, Mechanical Engineering department)')
        self.stdout.write('  student1 / student123   (CSE, semester 3; student2..student12 use the same password)')
        self.stdout.write('  student9, student10: Mechanical Engineering sem 2. student11: MCA sem 2. student12: CSE sem 4.')
