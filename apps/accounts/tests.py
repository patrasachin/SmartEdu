"""End-to-end tests: `python manage.py test`  (about 2 minutes)"""
import io
import json
import tempfile

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail.backends.base import BaseEmailBackend
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.departments import DEPARTMENTS, department_choices, semester_count
from apps.accounts.models import User, StudentProfile
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.exams.models import Exam, ExamSubmission, Question
from apps.materials.models import StudyMaterial
from apps.notifications.models import EmailLog
from apps.performance.models import WeakTopic
from apps.performance.series import performance_series
from apps.proctoring.models import ProctoringLog
from apps.reattempt.models import ReattemptRequest

CSE, ME = 'Computer Science and Engineering (CSE)', 'Mechanical Engineering'
MBA, MCA = 'Master of Business Administration (MBA)', 'Master of Computer Applications (MCA)'
PDF = b'%PDF-1.4 demo'


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)

    def login(self, username, password=None):
        self.client.logout()
        pw = password or ('admin123' if username == 'admin' else 'teacher123' if username.startswith('teacher') else 'student123')
        self.assertTrue(self.client.login(username=username, password=pw))

    def post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    def closed_exam(self, dept=CSE, teacher='teacher1'):
        """A published exam whose closing time has already passed."""
        t = User.objects.get(username=teacher)
        e = Exam.objects.create(title='Closed Quiz', subject='Maths', department=dept, semester=3, duration_minutes=15, status='PUBLISHED', created_by=t,
                                scheduled_at=timezone.now() - timezone.timedelta(days=1), closes_at=timezone.now() - timezone.timedelta(hours=1))
        Question.objects.create(exam=e, qtype='MCQ', text='1+1?', topic='Basics', marks=5, option_a='1', option_b='2', option_c='3',
                                option_d='4', correct_option='B')
        e.total_marks = 5; e.save()
        return e


# ======================================================================= core flows
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class FlowTests(Base):
    def test_public_pages_and_branding(self):
        r = self.client.get('/')
        self.assertContains(r, 'SmartEdu')
        self.assertNotContains(r, 'EduAI')
        for url in ['/auth/login/', '/auth/forgot-password/', '/auth/register/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_login_redirects_by_role(self):
        for u, p, dest in [('admin', 'admin123', '/admin-portal/dashboard/'), ('teacher1', 'teacher123', '/teacher/dashboard/'),
                           ('student1', 'student123', '/student/dashboard/')]:
            self.client.logout()
            self.assertRedirects(self.client.post('/auth/login/', {'username': u, 'password': p}), dest, fetch_redirect_response=False)
        self.client.logout()
        self.assertContains(self.client.post('/auth/login/', {'username': 'admin', 'password': 'nope'}), 'Wrong username or password')

    def test_forgot_password_notifies_admin(self):
        self.client.post('/auth/forgot-password/', {'username': 'student1', 'note': ''})
        self.assertTrue(User.objects.get(username='admin').notifications.filter(title__icontains='reset').exists())

    def test_all_pages_render(self):
        pages = {
            'admin': ['/admin-portal/dashboard/', '/admin-portal/students/', '/admin-portal/teachers/', '/admin-portal/departments/', '/admin-portal/exams/',
                      '/admin-portal/announce/', '/admin-portal/emails/', '/notifications/', '/auth/password/'],
            'teacher1': ['/teacher/dashboard/', '/teacher/exams/', '/teacher/create-exam/', '/teacher/results/', '/teacher/students/',
                         '/teacher/attendance/', '/teacher/performance/', '/materials/', '/materials/upload/', '/assignments/', '/assignments/new/',
                         '/reattempt/', '/notifications/'],
            'student1': ['/student/dashboard/', '/student/exams/', '/student/attendance/', '/student/performance/', '/materials/',
                         '/assignments/', '/reattempt/', '/notifications/'],
        }
        for u, urls in pages.items():
            self.login(u)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 200, f'{u} {url}')

    def test_teacher_detail_pages(self):
        self.login('teacher1')
        exam = Exam.objects.filter(created_by__username='teacher1', status='PUBLISHED').first()
        sub = ExamSubmission.objects.filter(exam__created_by__username='teacher1').first()
        stu = User.objects.get(username='student1')
        for url in [f'/teacher/exams/{exam.id}/questions/', f'/teacher/exams/{exam.id}/answer-key/', f'/teacher/exams/{exam.id}/edit/',
                    f'/teacher/results/{exam.id}/', f'/teacher/submission/{sub.id}/', f'/teacher/students/{stu.id}/',
                    '/teacher/results/?filter=low', '/teacher/students/?filter=low']:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_roles_are_enforced(self):
        self.login('student1')
        for url in ['/teacher/dashboard/', '/teacher/results/', '/admin-portal/dashboard/', '/admin-portal/emails/', '/assignments/new/',
                    '/materials/upload/']:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.login('teacher1')
        for url in ['/student/dashboard/', '/admin-portal/students/']:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.logout()
        self.assertEqual(self.client.get('/student/dashboard/').status_code, 302)

    def test_teacher_cannot_touch_other_teachers_exam(self):
        other = Exam.objects.filter(created_by__username='teacher2').first()
        self.login('teacher1')
        self.assertEqual(self.client.get(f'/teacher/exams/{other.id}/questions/').status_code, 404)

    # ---- exam lifecycle with closing time and guardian email -----------------
    def test_exam_lifecycle_and_guardian_result_email(self):
        self.login('teacher1')
        opens = (timezone.localtime() - timezone.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        closes = (timezone.localtime() + timezone.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        base = {'title': 'Test Exam', 'subject': 'Maths', 'department': CSE, 'semester': 3, 'duration_minutes': 15, 'scheduled_at': opens, 'description': ''}
        bad = self.client.post('/teacher/create-exam/', {**base, 'closes_at': opens})
        self.assertContains(bad, 'closing time must be after')
        self.assertEqual(self.client.post('/teacher/create-exam/', base).status_code, 200)       # closing time is required
        r = self.client.post('/teacher/create-exam/', {**base, 'closes_at': closes})
        exam = Exam.objects.get(title='Test Exam')
        self.assertRedirects(r, f'/teacher/exams/{exam.id}/questions/', fetch_redirect_response=False)
        self.assertEqual(exam.status, 'DRAFT'); self.assertIsNotNone(exam.closes_at)
        self.client.post(f'/teacher/exams/{exam.id}/publish/'); exam.refresh_from_db()
        self.assertEqual(exam.status, 'DRAFT')                                                    # empty exam cannot be published
        bad_q = self.client.post(f'/teacher/exams/{exam.id}/questions/', {'qtype': 'MCQ', 'topic': 'Algebra', 'text': 'Q?', 'marks': 5})
        self.assertEqual((bad_q.status_code, exam.questions.count()), (200, 0))
        self.client.post(f'/teacher/exams/{exam.id}/questions/', {'qtype': 'MCQ', 'topic': 'Algebra', 'text': '1+1?', 'marks': 5,
                         'option_a': '1', 'option_b': '2', 'option_c': '3', 'option_d': '4', 'correct_option': 'B'})
        self.client.post(f'/teacher/exams/{exam.id}/questions/', {'qtype': 'SUBJECTIVE', 'topic': 'Algebra', 'text': 'Define algebra', 'marks': 5,
                         'ideal_answer': 'Algebra uses symbols and variables', 'keywords': 'symbols, variables'})
        exam.refresh_from_db(); self.assertEqual((exam.total_marks, exam.exam_type), (10, 'MIXED'))
        self.client.post(f'/teacher/exams/{exam.id}/publish/'); exam.refresh_from_db()
        self.assertEqual(exam.status, 'PUBLISHED')
        self.assertTrue(User.objects.get(username='student2').notifications.filter(title__icontains='Test Exam').exists())
        self.assertFalse(User.objects.get(username='student9').notifications.filter(title__icontains='Test Exam').exists())   # other department and semester

        self.login('student1')
        self.assertEqual(self.client.get(f'/student/exams/{exam.id}/instructions/').status_code, 200)
        r = self.client.get(f'/student/exams/{exam.id}/take/'); self.assertEqual(r.status_code, 200)
        sub = ExamSubmission.objects.get(exam=exam, student__username='student1')
        qs = list(exam.questions.order_by('id'))
        answers = {str(qs[0].id): 'B', str(qs[1].id): 'Algebra uses symbols and variables'}
        self.assertTrue(self.post_json(f'/exams/save/{exam.id}/', {'answers': answers}).json()['success'])
        self.assertContains(self.client.get(f'/student/exams/{exam.id}/take/'), 'checked')
        mail.outbox.clear()
        data = self.post_json(f'/exams/submit/{exam.id}/', {'answers': answers}).json()
        self.assertTrue(data['success']); self.assertEqual(round(data['percentage']), 100)
        # the guardian got the result
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertEqual(m.to, ['guardian.student1@example.com'])
        for part in ['Parent of Aarav', 'Test Exam', '10 out of 10', '100.0%']:
            self.assertIn(part, m.subject + m.body)
        self.assertEqual(EmailLog.objects.filter(kind='RESULT', status='SENT', student__username='student1').count(), 1)
        self.post_json(f'/exams/submit/{exam.id}/', {'answers': {}})                              # submitting twice does nothing
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(sub.student.performance_reports.filter(exam=exam).count(), 1)
        self.assertEqual(self.client.get(f'/student/result/{sub.id}/').status_code, 200)

        self.login('teacher1')
        ans = sub.answers.get(question=qs[1])
        self.client.post(f'/teacher/submission/{sub.id}/', {f'score_{ans.id}': '2', f'feedback_{ans.id}': 'Too short'})
        sub.refresh_from_db(); self.assertEqual(sub.total_score, 7)

    def test_three_violations_cancel_exam_and_tell_guardian(self):
        exam = Exam.objects.get(title='Physics Basics Quiz')
        self.login('student1')
        self.client.get(f'/student/exams/{exam.id}/take/')
        sub = ExamSubmission.objects.get(exam=exam, student__username='student1')
        mail.outbox.clear()
        for i, expected in enumerate([False, False, True], start=1):
            r = self.post_json('/proctoring/log/', {'submission_id': sub.id, 'violation_type': 'TAB_SWITCH', 'details': 'x'})
            self.assertEqual((r.json()['count'], r.json()['cancelled']), (i, expected))
        sub.refresh_from_db(); self.assertTrue(sub.is_cancelled)
        self.assertEqual(len(mail.outbox), 1); self.assertIn('cancelled', mail.outbox[0].subject)
        self.assertRedirects(self.client.get(f'/student/exams/{exam.id}/take/'), f'/student/result/{sub.id}/', fetch_redirect_response=False)
        self.assertTrue(exam.created_by.notifications.filter(title__icontains='cancelled').exists())
        self.login('teacher2')
        self.client.post(f'/teacher/submission/{sub.id}/reset/')
        self.assertFalse(ExamSubmission.objects.filter(id=sub.id).exists())

    def test_bad_violation_type_rejected(self):
        exam = Exam.objects.get(title='Physics Basics Quiz')
        self.login('student1'); self.client.get(f'/student/exams/{exam.id}/take/')
        sub = ExamSubmission.objects.get(exam=exam, student__username='student1')
        self.assertEqual(self.post_json('/proctoring/log/', {'submission_id': sub.id, 'violation_type': 'HACK'}).status_code, 400)

    def test_frame_endpoint(self):
        from ai_engine.proctoring.face_detector import AVAILABLE
        if not AVAILABLE:
            self.skipTest('OpenCV is not installed, so the face check is off (the rest of the app works)')
        import cv2, numpy as np
        exam = Exam.objects.get(title='Physics Basics Quiz')
        self.login('student1'); self.client.get(f'/student/exams/{exam.id}/take/')
        sub = ExamSubmission.objects.get(exam=exam, student__username='student1')
        ok, buf = cv2.imencode('.jpg', np.zeros((240, 320, 3), dtype=np.uint8))
        f = io.BytesIO(buf.tobytes()); f.name = 'frame.jpg'
        for _ in range(3):
            f.seek(0); r = self.client.post('/proctoring/frame/', {'submission_id': sub.id, 'image': f})
        self.assertEqual(r.json().get('violation'), 'NO_FACE')
        self.assertEqual(ProctoringLog.objects.filter(submission=sub).count(), 1)

    def test_upcoming_draft_and_other_department(self):
        self.login('student1')
        up = Exam.objects.get(title='Chapter Test: Algebra Revision')
        self.assertRedirects(self.client.get(f'/student/exams/{up.id}/take/'), f'/student/exams/{up.id}/instructions/', fetch_redirect_response=False)
        self.assertEqual(self.client.get(f'/student/exams/{Exam.objects.get(title__startswith="Draft").id}/instructions/').status_code, 404)
        self.assertEqual(self.client.get(f'/student/exams/{Exam.objects.get(title="Unit Test: Basic Algebra").id}/instructions/').status_code, 403)

    # ---- attendance + guardian email ------------------------------------------
    def test_bulk_attendance_emails_guardians_once(self):
        self.login('teacher1')
        today = timezone.localdate().isoformat()
        students = list(User.objects.filter(role='STUDENT', student_profile__department=CSE, student_profile__semester=3).order_by('id'))
        data = {'department': CSE, 'semester': 3, 'date': today}
        for s in students:
            data[f'status_{s.id}'] = 'ABSENT' if s.username == 'student3' else 'LATE' if s.username == 'student5' else 'PRESENT'
        mail.outbox.clear()
        self.client.post('/teacher/attendance/', data)
        self.assertEqual(len(mail.outbox), len(students))
        by_to = {m.to[0]: m for m in mail.outbox}
        self.assertIn('ABSENT', by_to['guardian.student3@example.com'].body)
        self.assertIn('PRESENT (arrived late)', by_to['guardian.student5@example.com'].body)
        self.assertIn('PRESENT', by_to['guardian.student2@example.com'].body)
        self.assertTrue(User.objects.get(username='student3').notifications.filter(ntype='ATTENDANCE').exists())
        mail.outbox.clear()
        self.client.post('/teacher/attendance/', data)                                            # same again: nothing new is sent
        self.assertEqual(len(mail.outbox), 0)
        data[f'status_{User.objects.get(username="student2").id}'] = 'ABSENT'                       # one change: one email
        self.client.post('/teacher/attendance/', data)
        self.assertEqual(len(mail.outbox), 1); self.assertIn('ABSENT', mail.outbox[0].body)

    # ---- admin: department, guardian, edit ---------------------------------------
    def test_admin_register_student_department_semester_and_guardian(self):
        self.login('admin')
        base = {'username': 'newkid', 'first_name': 'New', 'last_name': 'Kid', 'roll_number': 'ME99',
                'guardian_name': 'Mr Kid', 'guardian_email': 'kid.parent@example.com'}
        url = '/admin-portal/students/register/'
        # guardian email is mandatory
        self.assertContains(self.client.post(url, {**base, 'guardian_email': '', 'department': ME, 'semester': 2}), "guardian&#x27;s email is required")
        self.assertFalse(User.objects.filter(username='newkid').exists())
        self.assertContains(self.client.post(url, {**base, 'guardian_email': 'not-an-email', 'department': ME, 'semester': 2}), 'valid email')
        # both drop-downs are required
        self.assertContains(self.client.post(url, {**base, 'department': '', 'semester': 2}), 'This field is required')
        self.assertContains(self.client.post(url, {**base, 'department': ME, 'semester': ''}), 'This field is required')
        # only the fixed departments are accepted
        self.assertContains(self.client.post(url, {**base, 'department': 'Class 9', 'semester': 2}), 'Select a valid choice')
        # a valid department and semester
        r = self.client.post(url, {**base, 'department': ME, 'semester': 8})
        self.assertRedirects(r, '/admin-portal/students/', fetch_redirect_response=False)
        p = User.objects.get(username='newkid').student_profile
        self.assertEqual((p.department, p.semester, p.guardian_email, p.guardian_name), (ME, 8, 'kid.parent@example.com', 'Mr Kid'))
        # MBA and MCA have only 4 semesters
        for dept in (MBA, MCA):
            self.assertContains(self.client.post(url, {**base, 'username': 'x5', 'roll_number': 'X5', 'department': dept, 'semester': 5}), 'only 4 semesters')
        r = self.client.post(url, {**base, 'username': 'mba4', 'roll_number': 'MBA4', 'department': MBA, 'semester': 4})
        self.assertRedirects(r, '/admin-portal/students/', fetch_redirect_response=False)
        self.assertEqual(User.objects.get(username='mba4').student_profile.semester, 4)
        self.assertContains(self.client.post(url, {**base, 'username': 'late9', 'roll_number': 'L9', 'department': ME, 'semester': 9}), 'Select a valid choice')
        # duplicates
        self.assertContains(self.client.post(url, {**base, 'department': ME, 'semester': 2}), 'already')

    def test_dropdowns_list_exactly_the_given_departments(self):
        self.login('admin')
        r = self.client.get('/admin-portal/students/')
        self.assertEqual(len(DEPARTMENTS), 17)
        for d in DEPARTMENTS:
            self.assertContains(r, d.replace('&', '&amp;'))
        for word in ['Class 8', 'Class 9', 'Class 10', 'Others']:
            self.assertNotContains(r, word)
        self.assertEqual((semester_count(MBA), semester_count(MCA), semester_count(CSE), semester_count('Food Technology')), (4, 4, 8, 8))
        for url in ['/teacher/create-exam/', '/materials/upload/', '/assignments/new/']:
            self.login('teacher1')
            page = self.client.get(url)
            self.assertContains(page, 'Food Technology'); self.assertContains(page, 'Semester'); self.assertNotContains(page, 'Class 10')

    def test_admin_edit_student_and_other_actions(self):
        self.login('admin')
        kid = User.objects.get(username='student1')
        self.assertEqual(self.client.get(f'/admin-portal/students/{kid.id}/edit/').status_code, 200)
        r = self.client.post(f'/admin-portal/students/{kid.id}/edit/', {'first_name': 'Aarav', 'last_name': 'Sharma', 'email': '', 'phone': '', 'department': ME,
                                                                        'semester': '6', 'guardian_name': 'New Guardian', 'guardian_email': 'new.guardian@example.com'})
        self.assertRedirects(r, '/admin-portal/students/', fetch_redirect_response=False)
        kid.student_profile.refresh_from_db()
        self.assertEqual((kid.student_profile.department, kid.student_profile.semester, kid.student_profile.guardian_email), (ME, 6, 'new.guardian@example.com'))
        self.assertContains(self.client.post(f'/admin-portal/students/{kid.id}/edit/', {'first_name': 'A', 'department': ME, 'semester': '2', 'guardian_name': 'x', 'guardian_email': ''}),
                            "guardian&#x27;s email is required")
        self.client.post(f'/admin-portal/users/{kid.id}/toggle/'); kid.refresh_from_db(); self.assertFalse(kid.is_active)
        self.client.post('/admin-portal/teachers/register/', {'username': 'newteach', 'first_name': 'N', 'employee_id': 'T999', 'subject': 'Art', 'department': 'Civil Engineering'})
        self.assertEqual(User.objects.get(username='newteach').role, 'TEACHER')
        self.assertEqual(User.objects.get(username='newteach').teacher_profile.department, 'Civil Engineering')
        self.client.post('/admin-portal/announce/', {'audience': 'DEPT', 'department': CSE, 'semester': '3', 'title': 'Holiday', 'message': 'Closed Friday'})
        self.assertTrue(User.objects.get(username='student2').notifications.filter(title='Holiday').exists())
        self.assertFalse(User.objects.get(username='student9').notifications.filter(title='Holiday').exists())
        self.assertFalse(User.objects.get(username='student12').notifications.filter(title='Holiday').exists())      # CSE but semester 4
        self.client.post('/admin-portal/announce/', {'audience': 'DEPT', 'department': CSE, 'semester': '', 'title': 'All CSE', 'message': 'Hello'})
        self.assertTrue(User.objects.get(username='student12').notifications.filter(title='All CSE').exists())

    def test_weak_topics_and_notifications_page(self):
        self.assertTrue(WeakTopic.objects.filter(student__username='student7').exists())
        self.login('student1')
        self.assertEqual(self.client.get('/notifications/').status_code, 200)
        self.assertEqual(self.client.get('/student/notifications/').status_code, 302)


# ======================================================================= guardian emails
class FailingBackend(BaseEmailBackend):
    def send_messages(self, messages):
        raise OSError('SMTP server refused the connection')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class EmailTests(Base):
    def test_failed_sending_is_logged_not_crashing(self):
        exam = Exam.objects.get(title='Physics Basics Quiz')
        self.login('student2'); self.client.get(f'/student/exams/{exam.id}/take/')
        with override_settings(EMAIL_BACKEND='apps.accounts.tests.FailingBackend'):
            data = self.post_json(f'/exams/submit/{exam.id}/', {'answers': {}}).json()
        self.assertTrue(data['success'])                                                         # the exam is still submitted
        log = EmailLog.objects.get(kind='RESULT', student__username='student2')
        self.assertEqual(log.status, 'FAILED'); self.assertIn('refused', log.error)
        self.login('admin')
        r = self.client.get('/admin-portal/emails/?status=FAILED')
        self.assertContains(r, 'refused'); self.assertContains(r, 'guardian.student2@example.com')

    def test_student_without_guardian_email_is_skipped(self):
        p = StudentProfile.objects.get(user__username='student2'); p.guardian_email = ''; p.save()
        exam = Exam.objects.get(title='Physics Basics Quiz')
        self.login('student2'); self.client.get(f'/student/exams/{exam.id}/take/')
        mail.outbox.clear()
        self.assertTrue(self.post_json(f'/exams/submit/{exam.id}/', {'answers': {}}).json()['success'])
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_email_log_and_test_email(self):
        self.login('admin')
        mail.outbox.clear()
        self.client.post('/admin-portal/emails/test/', {'to': 'me@example.com'})
        self.assertEqual(mail.outbox[0].to, ['me@example.com'])
        self.assertContains(self.client.get('/admin-portal/emails/'), 'SmartEdu test email')
        self.assertContains(self.client.post('/admin-portal/emails/test/', {'to': 'bad'}, follow=True), 'valid email')


# ======================================================================= study material (unchanged feature, department wording)
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MaterialTests(Base):
    def test_seeded_material_visible_only_to_its_department(self):
        self.login('student1')
        self.assertContains(self.client.get('/materials/'), 'Algebra formula sheet')
        self.assertNotContains(self.client.get('/materials/'), 'Basic algebra practice')         # Mechanical Engineering, semester 2
        pdf = StudyMaterial.objects.get(title='Algebra formula sheet')
        r = self.client.get(f'/materials/{pdf.id}/file/')
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'application/pdf'))
        self.assertTrue(b''.join(r.streaming_content).startswith(b'%PDF'))
        for other in ('student9', 'student12'):                                                  # other department / next semester
            self.login(other)
            self.assertEqual(self.client.get(f'/materials/{pdf.id}/file/').status_code, 403, other)

    def test_teacher_uploads_every_type_to_a_department_and_semester(self):
        self.login('teacher1')
        for name in ['notes.pdf', 'essay.docx', 'slides.pptx', 'marks.xlsx']:
            r = self.client.post('/materials/upload/', {'title': f'T {name}', 'subject': 'Maths', 'department': ME, 'semester': 2, 'description': 'd',
                                                         'file': SimpleUploadedFile(name, b'data-' + name.encode()), 'link': ''})
            self.assertRedirects(r, '/materials/', fetch_redirect_response=False)
            m = StudyMaterial.objects.get(title=f'T {name}')
            self.assertEqual((m.department, m.semester), (ME, 2))
        self.assertTrue(User.objects.get(username='student9').notifications.filter(title__startswith='New study material: T notes').exists())
        self.assertFalse(User.objects.get(username='student1').notifications.filter(title__startswith='New study material: T notes').exists())
        base = {'title': 'V', 'subject': 'M', 'department': CSE, 'semester': 3}
        self.assertContains(self.client.post('/materials/upload/', {**base, 'title': 'E'}), 'Attach a file, paste a link')
        self.assertContains(self.client.post('/materials/upload/', {**base, 'file': SimpleUploadedFile('v.exe', b'MZ')}), 'not allowed')
        self.assertContains(self.client.post('/materials/upload/', {'title': 'x', 'subject': 's', 'link': 'https://a.com'}), 'This field is required')
        self.assertContains(self.client.post('/materials/upload/', {**base, 'link': 'javascript:alert(1)'}), 'Enter a valid URL')
        self.assertContains(self.client.post('/materials/upload/', {**base, 'department': MCA, 'semester': 6, 'link': 'https://a.com'}), 'only 4 semesters')


# ======================================================================= assignments
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AssignmentTests(Base):
    def create(self, dept=CSE, sem=3, due=''):
        self.login('teacher1')
        self.client.post('/assignments/new/', {'title': 'Graph theory basics', 'subject': 'Maths', 'department': dept, 'semester': sem, 'due_date': due, 'description': ''})
        return Assignment.objects.get(title='Graph theory basics', department=dept, semester=sem)

    def test_teacher_sends_topic_only_and_students_see_it(self):
        a = self.create()
        self.assertEqual(a.created_by.username, 'teacher1')
        self.assertTrue(User.objects.get(username='student2').notifications.filter(ntype='ASSIGNMENT', title__contains='Graph theory').exists())
        self.assertFalse(User.objects.get(username='student9').notifications.filter(title__contains='Graph theory').exists())
        self.login('student1')
        self.assertContains(self.client.get('/assignments/'), 'Graph theory basics')
        for other in ('student9', 'student12'):                                                  # other department / same department, next semester
            self.login(other)
            self.assertNotContains(self.client.get('/assignments/'), 'Graph theory basics')
            self.assertEqual(self.client.get(f'/assignments/{a.id}/').status_code, 403, other)
            self.assertEqual(self.client.post(f'/assignments/{a.id}/submit/', {'file': SimpleUploadedFile('w.pdf', PDF)}).status_code, 403, other)
        self.login('teacher1')
        self.assertContains(self.client.post('/assignments/new/', {'title': '', 'subject': 's'}), 'This field is required')

    def test_submit_validation_late_and_resubmit(self):
        a = self.create()
        self.login('student1')
        url = f'/assignments/{a.id}/submit/'
        self.assertContains(self.client.post(url, {'note': 'x'}), 'This field is required')
        self.assertContains(self.client.post(url, {'file': SimpleUploadedFile('virus.exe', b'MZ')}), 'not allowed')
        self.assertContains(self.client.post(url, {'file': SimpleUploadedFile('big.pdf', b'0' * (16 * 1024 * 1024))}), 'too large')
        for name, kind in [('work.pdf', 'PDF'), ('scan.png', 'Photo')]:
            AssignmentSubmission.objects.filter(assignment=a).delete()
            r = self.client.post(url, {'file': SimpleUploadedFile(name, PDF), 'note': 'done'})
            self.assertRedirects(r, f'/assignments/{a.id}/', fetch_redirect_response=False)
            self.assertEqual(AssignmentSubmission.objects.get(assignment=a, student__username='student1').kind[0], kind)
        sub = AssignmentSubmission.objects.get(assignment=a, student__username='student1'); old = sub.file.name
        self.client.post(url, {'file': SimpleUploadedFile('newer.docx', PDF)})                     # replace before review
        sub.refresh_from_db()
        self.assertEqual(AssignmentSubmission.objects.filter(assignment=a).count(), 1)
        self.assertTrue(sub.filename.startswith('newer')); self.assertFalse(sub.file.storage.exists(old))
        self.assertTrue(a.created_by.notifications.filter(title__startswith='Assignment submitted').exists())
        # late work is accepted but marked late
        late = Assignment.objects.create(title='Old one', subject='M', department=CSE, semester=3, created_by=a.created_by, due_date=timezone.now() - timezone.timedelta(days=1))
        self.client.post(f'/assignments/{late.id}/submit/', {'file': SimpleUploadedFile('l.pdf', PDF)})
        self.assertTrue(AssignmentSubmission.objects.get(assignment=late, student__username='student1').is_late)

    def test_teacher_reviews_and_student_sees_rating(self):
        a = self.create()
        self.login('student1'); self.client.post(f'/assignments/{a.id}/submit/', {'file': SimpleUploadedFile('w.pdf', PDF)})
        sub = AssignmentSubmission.objects.get(assignment=a, student__username='student1')
        self.login('teacher1')
        page = self.client.get(f'/assignments/{a.id}/')
        self.assertContains(page, 'Waiting for review'); self.assertContains(page, 'Not submitted')   # the other students
        self.assertEqual(self.client.get(f'/assignments/submission/{sub.id}/review/').status_code, 200)
        self.assertContains(self.client.post(f'/assignments/submission/{sub.id}/review/', {'review': 'ok'}), 'Choose a rating')
        r = self.client.post(f'/assignments/submission/{sub.id}/review/', {'rating': 4, 'review': 'Very good work'})
        self.assertRedirects(r, f'/assignments/{a.id}/', fetch_redirect_response=False)
        sub.refresh_from_db(); self.assertEqual((sub.rating, sub.review), (4, 'Very good work'))
        self.login('student1')
        detail = self.client.get(f'/assignments/{a.id}/')
        self.assertContains(detail, '4 / 5'); self.assertContains(detail, 'Very good work')
        self.assertContains(self.client.get('/assignments/?filter=reviewed'), 'Graph theory basics')
        self.assertTrue(User.objects.get(username='student1').notifications.filter(title__startswith='Assignment reviewed').exists())
        before = sub.file.name
        self.client.post(f'/assignments/{a.id}/submit/', {'file': SimpleUploadedFile('again.pdf', PDF)})   # locked after review
        sub.refresh_from_db(); self.assertEqual(sub.file.name, before)
        for u in ['student2', 'student9', 'teacher2']:
            self.login(u)
            self.assertIn(self.client.get(f'/assignments/submission/{sub.id}/review/').status_code, (403, 404))
        self.login('teacher2'); self.assertEqual(self.client.get(f'/assignments/submission/{sub.id}/file/').status_code, 403)

    def test_file_permissions_and_delete(self):
        a = self.create()
        self.login('student1'); self.client.post(f'/assignments/{a.id}/submit/', {'file': SimpleUploadedFile('w.pdf', PDF)})
        sub = AssignmentSubmission.objects.get(assignment=a, student__username='student1')
        url = f'/assignments/submission/{sub.id}/file/'
        for u, code in [('student1', 200), ('teacher1', 200), ('admin', 200), ('student2', 403), ('teacher2', 403)]:
            self.login(u); self.assertEqual(self.client.get(url).status_code, code, u)
        name = sub.file.name
        self.login('teacher2'); self.assertEqual(self.client.post(f'/assignments/{a.id}/delete/').status_code, 404)
        self.login('teacher1'); self.client.post(f'/assignments/{a.id}/delete/')
        self.assertFalse(Assignment.objects.filter(id=a.id).exists()); self.assertFalse(sub.file.storage.exists(name))


# ======================================================================= missed exams and re-attempt requests
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ReattemptTests(Base):
    good = {'reason': 'I was in hospital on the day of the exam and could not log in.'}

    def proof(self, name='proof.pdf'):
        return SimpleUploadedFile(name, PDF)

    def test_missed_states_from_demo_data(self):
        e6 = Exam.objects.get(title='Matrices Mid-term Quiz')
        for user, expected in [('student1', 302), ('student7', 302), ('student4', 200), ('student2', 302)]:   # student2 already finished it
            self.login(user)
            self.assertEqual(self.client.get(f'/student/exams/{e6.id}/take/').status_code, expected, user)
        self.login('student2')
        self.assertIn('/student/result/', self.client.get(f'/student/exams/{e6.id}/take/')['Location'])
        self.login('student1')
        self.assertContains(self.client.get(f'/student/exams/{e6.id}/instructions/'), 'waiting for your teacher')
        self.login('student7')
        self.assertContains(self.client.get(f'/student/exams/{e6.id}/instructions/'), 'not approved')
        self.assertContains(self.client.get('/reattempt/'), 'does not cover the exam date')
        self.login('student4')
        self.assertContains(self.client.get(f'/student/exams/{e6.id}/instructions/'), 'Only you can take it')
        self.login('student8')                                                                   # missed it and has not asked yet
        self.assertContains(self.client.get('/student/dashboard/'), 'You missed')
        self.assertContains(self.client.get(f'/student/exams/{e6.id}/instructions/'), 'Give your reason and proof')

    def test_student_requests_with_reason_and_proof(self):
        e = self.closed_exam()
        self.login('student2')
        self.assertContains(self.client.get(f'/student/exams/{e.id}/instructions/'), 'did not attempt')
        self.assertRedirects(self.client.get(f'/student/exams/{e.id}/take/'), f'/student/exams/{e.id}/instructions/', fetch_redirect_response=False)
        self.assertContains(self.client.get('/reattempt/'), 'Closed Quiz')
        url = f'/reattempt/new/{e.id}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.post(url, {'reason': 'sick', 'proof': self.proof()}), 'at least 15')
        self.assertContains(self.client.post(url, self.good), 'This field is required')               # proof is mandatory
        self.assertContains(self.client.post(url, {**self.good, 'proof': self.proof('x.exe')}), 'not allowed')
        self.assertFalse(ReattemptRequest.objects.filter(exam=e).exists())
        r = self.client.post(url, {**self.good, 'proof': self.proof('certificate.pdf')})
        self.assertRedirects(r, '/reattempt/', fetch_redirect_response=False)
        req = ReattemptRequest.objects.get(exam=e, student__username='student2')
        self.assertEqual(req.status, 'PENDING'); self.assertEqual(req.proof_name[:11], 'certificate')
        self.assertTrue(e.created_by.notifications.filter(ntype='REATTEMPT', title__contains='Closed Quiz').exists())
        self.assertContains(self.client.post(url, {**self.good, 'proof': self.proof()}, follow=True), 'already sent')
        # a live exam cannot be "missed"
        live = Exam.objects.get(title='Physics Basics Quiz')
        self.assertContains(self.client.get(f'/reattempt/new/{live.id}/', follow=True), 'only ask for another chance')

    def test_teacher_approves_only_that_student(self):
        e = self.closed_exam()
        self.login('student2'); self.client.post(f'/reattempt/new/{e.id}/', {**self.good, 'proof': self.proof()})
        req = ReattemptRequest.objects.get(exam=e, student__username='student2')
        self.login('teacher1')
        self.assertContains(self.client.get('/reattempt/'), 'I was in hospital')
        self.assertContains(self.client.get('/teacher/dashboard/'), 'waiting')
        future = (timezone.localtime() + timezone.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        past = (timezone.localtime() - timezone.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        url = f'/reattempt/{req.id}/decide/'
        self.client.post(url, {'action': 'approve'}); req.refresh_from_db(); self.assertEqual(req.status, 'PENDING')              # needs a time
        self.client.post(url, {'action': 'approve', 'extended_until': past}); req.refresh_from_db(); self.assertEqual(req.status, 'PENDING')
        self.client.post(url, {'action': 'reject'}); req.refresh_from_db(); self.assertEqual(req.status, 'PENDING')              # needs a reason
        self.login('teacher2'); self.assertEqual(self.client.post(url, {'action': 'approve', 'extended_until': future}).status_code, 404)
        self.login('teacher1')
        self.client.post(url, {'action': 'approve', 'extended_until': future, 'comment': 'Get well soon'})
        req.refresh_from_db()
        self.assertEqual((req.status, req.decided_by.username), ('APPROVED', 'teacher1')); self.assertTrue(req.chance_is_open)
        self.assertTrue(User.objects.get(username='student2').notifications.filter(title__startswith='Re-attempt approved').exists())
        self.client.post(url, {'action': 'reject', 'comment': 'x'}); req.refresh_from_db(); self.assertEqual(req.status, 'APPROVED')    # cannot decide twice
        # only student2 can take the closed exam; student3 is still locked out
        self.login('student3'); self.assertEqual(self.client.get(f'/student/exams/{e.id}/take/').status_code, 302)
        self.login('student2'); self.assertEqual(self.client.get(f'/student/exams/{e.id}/take/').status_code, 200)
        sub = ExamSubmission.objects.get(exam=e, student__username='student2')
        qid = str(e.questions.first().id)
        self.assertTrue(self.post_json(f'/exams/submit/{e.id}/', {'answers': {qid: 'B'}}).json()['success'])
        sub.refresh_from_db(); self.assertTrue(sub.is_completed); self.assertEqual(sub.percentage, 100)
        self.assertContains(self.client.get('/student/exams/'), 'Completed')

    def test_reject_and_expired_chance(self):
        e = self.closed_exam()
        self.login('student2'); self.client.post(f'/reattempt/new/{e.id}/', {**self.good, 'proof': self.proof()})
        req = ReattemptRequest.objects.get(exam=e, student__username='student2')
        self.login('teacher1')
        self.client.post(f'/reattempt/{req.id}/decide/', {'action': 'reject', 'comment': 'Proof is unclear'})
        req.refresh_from_db(); self.assertEqual((req.status, req.teacher_comment), ('REJECTED', 'Proof is unclear'))
        self.login('student2'); self.assertEqual(self.client.get(f'/student/exams/{e.id}/take/').status_code, 302)
        self.assertContains(self.client.get('/reattempt/'), 'Proof is unclear')
        # an approved chance that has run out closes the door again
        req.status, req.extended_until = 'APPROVED', timezone.now() - timezone.timedelta(minutes=1); req.save()
        self.assertEqual(self.client.get(f'/student/exams/{e.id}/take/').status_code, 302)

    def test_proof_download_permissions_and_nav_badges(self):
        req = ReattemptRequest.objects.get(student__username='student1')
        url = f'/reattempt/{req.id}/proof/'
        for u, code in [('student1', 200), ('teacher1', 200), ('admin', 200), ('student2', 403), ('teacher2', 403)]:
            self.login(u); self.assertEqual(self.client.get(url).status_code, code, u)
        self.login('teacher1'); self.assertContains(self.client.get('/reattempt/'), 'Aarav Sharma')
        self.login('student5')
        self.assertEqual(self.client.get('/reattempt/').status_code, 200)

    def test_missed_banner_on_student_dashboard(self):
        e = self.closed_exam()
        self.login('student2')
        self.assertContains(self.client.get('/student/dashboard/'), 'You missed')


# ======================================================================= performance graph
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PerformanceGraphTests(Base):
    def test_series_combines_exams_and_assignment_ratings(self):
        s = performance_series(User.objects.get(username='student2'))
        c = s['chart']
        self.assertTrue(s['has_data']); self.assertGreater(s['exam_count'], 0); self.assertGreater(s['assignment_count'], 0)
        self.assertEqual(len(c['labels']), len(c['exams']), len(c['assignments']))
        self.assertTrue(any(v is not None for v in c['exams'])); self.assertTrue(any(v is not None for v in c['assignments']))
        self.assertTrue(all(v is None or 0 <= v <= 100 for v in c['assignments']))
        self.assertTrue(any(t.startswith('Assignment: ') for t in c['titles'])); self.assertTrue(any(t.startswith('Exam: ') for t in c['titles']))
        parts = [s['exam_avg'], s['rating_avg'] * 20]
        self.assertAlmostEqual(s['overall'], round(sum(parts) / 2, 1), places=1)

    def test_graph_on_student_and_teacher_pages(self):
        stu = User.objects.get(username='student2')
        self.login('student2')
        r = self.client.get('/student/performance/')
        self.assertContains(r, 'id="combined"'); self.assertContains(r, 'Assignment ratings'); self.assertContains(r, 'Overall')
        self.login('teacher1')
        r = self.client.get(f'/teacher/students/{stu.id}/')
        self.assertContains(r, 'id="combined"'); self.assertContains(r, 'Assignment rating')

    def test_new_review_changes_the_graph(self):
        stu = User.objects.get(username='student1')
        before = performance_series(stu)['assignment_count']
        a = Assignment.objects.create(title='Extra', subject='M', department=CSE, semester=3, created_by=User.objects.get(username='teacher1'))
        AssignmentSubmission.objects.create(assignment=a, student=stu, file=SimpleUploadedFile('a.pdf', PDF), rating=5, reviewed_at=timezone.now())
        after = performance_series(stu)
        self.assertEqual(after['assignment_count'], before + 1); self.assertEqual(after['chart']['assignments'][-1], 100)

    def test_student_with_no_data_sees_empty_state(self):
        self.login('admin')
        self.client.post('/admin-portal/students/register/', {'username': 'fresh', 'first_name': 'F', 'roll_number': 'F1', 'department': CSE, 'semester': 3,
                                                              'guardian_name': 'G', 'guardian_email': 'g@example.com', 'password': 'fresh-pass-1'})
        self.login('fresh', 'fresh-pass-1')
        self.assertContains(self.client.get('/student/performance/'), 'to see your graph')


# ======================================================================= department and semester
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DepartmentSemesterTests(Base):
    def test_no_pending_migrations(self):
        call_command('makemigrations', check=True, dry_run=True, verbosity=0)        # models and migrations agree

    def test_students_only_see_their_own_department_and_semester(self):
        sem3 = Exam.objects.get(title='Physics Basics Quiz')                         # CSE, semester 3
        me2 = Exam.objects.get(title='Unit Test: Basic Algebra')                     # Mechanical, semester 2
        self.login('student1')
        self.assertContains(self.client.get('/student/exams/'), 'Physics Basics Quiz')
        self.assertEqual(self.client.get(f'/student/exams/{sem3.id}/instructions/').status_code, 200)
        self.assertEqual(self.client.get(f'/student/exams/{me2.id}/instructions/').status_code, 403)
        self.login('student12')                                                      # CSE, but semester 4
        self.assertNotContains(self.client.get('/student/exams/'), 'Physics Basics Quiz')
        self.assertEqual(self.client.get(f'/student/exams/{sem3.id}/instructions/').status_code, 403)
        self.assertEqual(self.client.get(f'/student/exams/{sem3.id}/take/').status_code, 403)
        self.assertNotContains(self.client.get('/materials/'), 'Algebra formula sheet')
        self.assertNotContains(self.client.get('/assignments/'), 'Matrix operations')
        self.login('student9')                                                       # Mechanical, semester 2
        self.assertNotContains(self.client.get('/materials/'), 'Algebra formula sheet')
        self.assertContains(self.client.get('/materials/'), 'Basic algebra practice')

    def test_exam_is_sent_to_department_and_semester(self):
        self.login('teacher1')
        opens = (timezone.localtime() - timezone.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        closes = (timezone.localtime() + timezone.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        base = {'title': 'Sem 4 Exam', 'subject': 'Maths', 'duration_minutes': 15, 'scheduled_at': opens, 'closes_at': closes, 'description': ''}
        for bad in [{'department': CSE, 'semester': ''}, {'department': '', 'semester': 4}, {'department': MCA, 'semester': 6}, {'department': 'Class 8', 'semester': 4}]:
            self.assertEqual(self.client.post('/teacher/create-exam/', {**base, **bad}).status_code, 200, bad)
        self.assertFalse(Exam.objects.filter(title='Sem 4 Exam').exists())
        self.client.post('/teacher/create-exam/', {**base, 'department': CSE, 'semester': 4})
        e = Exam.objects.get(title='Sem 4 Exam'); self.assertEqual((e.department, e.semester), (CSE, 4))
        Question.objects.create(exam=e, qtype='MCQ', text='q', topic='t', marks=1, option_a='a', option_b='b', option_c='c', option_d='d', correct_option='A')
        self.client.post(f'/teacher/exams/{e.id}/publish/')
        self.assertTrue(User.objects.get(username='student12').notifications.filter(title__icontains='Sem 4 Exam').exists())
        self.assertFalse(User.objects.get(username='student1').notifications.filter(title__icontains='Sem 4 Exam').exists())
        self.assertContains(self.client.get(f'/teacher/exams/{e.id}/edit/'), 'Semester')
        self.client.post(f'/teacher/exams/{e.id}/edit/', {**base, 'department': CSE, 'semester': 5})   # teacher can change it before students start
        e.refresh_from_db(); self.assertEqual(e.semester, 5)

    def test_teacher_department_limit_setting(self):
        self.login('teacher1')
        page = self.client.get('/assignments/new/')
        self.assertContains(page, '<option value="Mechanical Engineering"')            # by default a teacher can send to any department
        with override_settings(TEACHER_LIMIT_TO_OWN_DEPARTMENT=True):
            page = self.client.get('/assignments/new/')
            self.assertContains(page, '<option value="Computer Science and Engineering (CSE)"'); self.assertNotContains(page, '<option value="Mechanical Engineering"')
            r = self.client.post('/assignments/new/', {'title': 'T', 'subject': 's', 'department': ME, 'semester': 2})
            self.assertContains(r, 'Select a valid choice')

    def test_admin_changes_a_students_semester_and_content_follows(self):
        self.login('admin')
        kid = User.objects.get(username='student12')
        base = {'first_name': 'Pooja', 'last_name': 'Iyer', 'email': '', 'phone': '', 'department': CSE,
                'guardian_name': 'Parent', 'guardian_email': 'g12@example.com'}
        exam = Exam.objects.get(title='Physics Basics Quiz')
        self.login('student12'); self.assertEqual(self.client.get(f'/student/exams/{exam.id}/instructions/').status_code, 403)
        self.login('admin')
        self.client.post(f'/admin-portal/students/{kid.id}/edit/', {**base, 'semester': '3'})
        kid.student_profile.refresh_from_db(); self.assertEqual(kid.student_profile.semester, 3)
        self.assertTrue(kid.notifications.filter(title='Your semester was updated').exists())
        self.login('student12')                                                      # now sees the semester 3 work
        self.assertEqual(self.client.get(f'/student/exams/{exam.id}/instructions/').status_code, 200)
        self.assertContains(self.client.get('/materials/'), 'Algebra formula sheet')
        self.assertContains(self.client.get('/assignments/'), 'Matrix operations')
        self.login('admin')                                                          # move up again: semester 3 work disappears
        self.client.post(f'/admin-portal/students/{kid.id}/edit/', {**base, 'semester': '4'})
        self.login('student12'); self.assertNotContains(self.client.get('/materials/'), 'Algebra formula sheet')
        # changing department too, and the semester limit of MCA
        self.login('admin')
        self.assertContains(self.client.post(f'/admin-portal/students/{kid.id}/edit/', {**base, 'department': MCA, 'semester': '6'}), 'only 4 semesters')
        self.client.post(f'/admin-portal/students/{kid.id}/edit/', {**base, 'department': MCA, 'semester': '2'})
        kid.student_profile.refresh_from_db(); self.assertEqual((kid.student_profile.department, kid.student_profile.semester), (MCA, 2))
        # list filters
        r = self.client.get('/admin-portal/students/', {'department': ME, 'semester': '2'})
        self.assertContains(r, 'student9'); self.assertNotContains(r, 'guardian.student1@example.com')
        self.assertEqual(self.client.get('/admin-portal/departments/').status_code, 200)
        self.assertContains(self.client.get('/admin-portal/departments/'), 'Semester 2')

    def test_admin_registers_and_updates_a_teacher_in_a_department(self):
        self.login('admin')
        base = {'username': 'tnew', 'first_name': 'Tina', 'last_name': 'Roy', 'employee_id': 'T777', 'subject': 'Chemistry'}
        url = '/admin-portal/teachers/register/'
        self.assertContains(self.client.post(url, base), 'This field is required')                       # department required
        self.assertContains(self.client.post(url, {**base, 'department': 'Class 8'}), 'Select a valid choice')
        r = self.client.post(url, {**base, 'department': 'Chemical Engineering'})
        self.assertRedirects(r, '/admin-portal/teachers/', fetch_redirect_response=False)
        t = User.objects.get(username='tnew')
        self.assertEqual(t.teacher_profile.department, 'Chemical Engineering')
        self.assertContains(self.client.get('/admin-portal/teachers/'), 'Chemical Engineering')
        self.assertContains(self.client.get('/admin-portal/teachers/', {'department': 'Chemical Engineering'}), 'tnew')
        self.assertNotContains(self.client.get('/admin-portal/teachers/', {'department': 'Food Technology'}), 'tnew')
        edit = f'/admin-portal/teachers/{t.id}/edit/'
        self.assertEqual(self.client.get(edit).status_code, 200)
        self.assertContains(self.client.post(edit, {'first_name': 'Tina', 'employee_id': 'T001', 'subject': 'Chemistry', 'department': 'Food Technology'}), 'already exists')
        self.client.post(edit, {'first_name': 'Tina', 'last_name': 'Roy', 'email': 't@example.com', 'phone': '', 'employee_id': 'T777',
                                'subject': 'Food Chemistry', 'department': 'Food Technology'})
        t.teacher_profile.refresh_from_db()
        self.assertEqual((t.teacher_profile.department, t.teacher_profile.subject), ('Food Technology', 'Food Chemistry'))

    def test_admin_deletes_a_student_with_confirmation_and_files(self):
        stu = User.objects.get(username='student1')
        sub = AssignmentSubmission.objects.filter(student=stu).first()
        proof = ReattemptRequest.objects.get(student=stu)
        files = [sub.file.name, proof.proof.name]; storage = sub.file.storage
        self.assertTrue(all(storage.exists(f) for f in files))
        self.login('admin')
        page = self.client.get(f'/admin-portal/users/{stu.id}/delete/')
        self.assertContains(page, 'permanently removes'); self.assertContains(page, 'exam attempts')
        self.assertTrue(User.objects.filter(id=stu.id).exists())                                        # GET alone deletes nothing
        r = self.client.post(f'/admin-portal/users/{stu.id}/delete/')
        self.assertRedirects(r, '/admin-portal/students/', fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(id=stu.id).exists())
        self.assertFalse(StudentProfile.objects.filter(user_id=stu.id).exists())
        self.assertFalse(ExamSubmission.objects.filter(student_id=stu.id).exists())
        self.assertFalse(any(storage.exists(f) for f in files))                                         # uploaded files were removed too
        self.assertEqual(User.objects.filter(role='STUDENT', student_profile__department=CSE).count(), 8)   # others untouched

    def test_admin_deletes_a_teacher(self):
        t = User.objects.get(username='teacher2')
        n_exams = Exam.objects.filter(created_by=t).count(); self.assertGreater(n_exams, 0)
        self.login('admin')
        page = self.client.get(f'/admin-portal/users/{t.id}/delete/')
        self.assertContains(page, 'exams they created'); self.assertContains(page, 'permanently removes')
        self.client.post(f'/admin-portal/users/{t.id}/delete/')
        self.assertFalse(User.objects.filter(id=t.id).exists())
        self.assertFalse(Exam.objects.filter(title='Physics Basics Quiz').exists())
        self.assertTrue(User.objects.get(username='teacher1'))
        # only students and teachers can be deleted, and only by an admin
        admin = User.objects.get(username='admin')
        self.assertEqual(self.client.post(f'/admin-portal/users/{admin.id}/delete/').status_code, 404)
        self.login('teacher1')
        self.assertEqual(self.client.post(f'/admin-portal/users/{User.objects.get(username="student2").id}/delete/').status_code, 403)

    def test_attendance_is_marked_per_department_and_semester(self):
        self.login('teacher1')
        r = self.client.get('/teacher/attendance/', {'department': CSE, 'semester': 4})
        self.assertContains(r, 'Pooja Iyer'); self.assertNotContains(r, 'Aarav Sharma')
        r = self.client.get('/teacher/attendance/', {'department': CSE, 'semester': 3})
        self.assertContains(r, 'Aarav Sharma'); self.assertNotContains(r, 'Pooja Iyer')
        mail.outbox.clear()
        self.client.post('/teacher/attendance/', {'department': CSE, 'semester': 4, 'date': timezone.localdate().isoformat(),
                                                   f'status_{User.objects.get(username="student12").id}': 'ABSENT'})
        self.assertEqual(len(mail.outbox), 1); self.assertIn('Semester 4', mail.outbox[0].body)
        from apps.attendance.models import Attendance
        self.assertEqual(Attendance.objects.filter(student__username='student12').first().semester, 4)
        self.assertEqual(self.client.get('/teacher/attendance/', {'department': 'Nonsense', 'semester': 99}).status_code, 200)   # bad input is tolerated

    def test_teacher_student_list_filters(self):
        self.login('teacher1')
        r = self.client.get('/teacher/students/', {'department': CSE, 'semester': '4'})
        self.assertContains(r, 'Pooja Iyer'); self.assertNotContains(r, 'Aarav Sharma')
        r = self.client.get('/teacher/students/', {'department': MCA})
        self.assertContains(r, 'Nikhil Rao')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class UpgradeTests(Base):
    def test_upgrade_departments_command_maps_old_names(self):
        StudentProfile.objects.filter(user__username='student1').update(department='Computer Science Engineering')
        StudentProfile.objects.filter(user__username='student2').update(department='Class 10')
        Exam.objects.filter(title='Physics Basics Quiz').update(department='Computer Science Engineering')
        from django.core.management import call_command as cc
        out = io.StringIO(); cc('upgrade_departments', stdout=out)
        self.assertEqual(StudentProfile.objects.get(user__username='student1').department, CSE)
        self.assertEqual(Exam.objects.get(title='Physics Basics Quiz').department, CSE)
        self.assertEqual(StudentProfile.objects.get(user__username='student2').department, 'Class 10')   # unknown: left alone and reported
        self.assertIn('Class 10', out.getvalue()); self.assertIn('2 record(s) renamed', out.getvalue())
        self.login('admin')                                                                              # and the admin can then fix it by hand
        sid = User.objects.get(username='student2').id
        self.assertEqual(self.client.get(f'/admin-portal/students/{sid}/edit/').status_code, 200)
