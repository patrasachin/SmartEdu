from django.db import models
from apps.accounts.models import User

class Exam(models.Model):
    EXAM_TYPE = (('MCQ','MCQ'),('SUBJECTIVE','Subjective'),('MIXED','Mixed'))
    STATUS = (('DRAFT','Draft'),('PUBLISHED','Published'),('COMPLETED','Completed'))
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=100)
    department = models.CharField('Department', max_length=100)
    semester = models.PositiveSmallIntegerField('Semester', default=1)
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE, default='MCQ')
    total_marks = models.IntegerField(default=100)
    duration_minutes = models.IntegerField(default=60)
    scheduled_at = models.DateTimeField()
    closes_at = models.DateTimeField(null=True, blank=True)   # last moment a student may start the exam
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_exams')
    status = models.CharField(max_length=20, choices=STATUS, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.subject}"

class Question(models.Model):
    QTYPE = (('MCQ','MCQ'),('SUBJECTIVE','Subjective'))
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    qtype = models.CharField(max_length=20, choices=QTYPE, default='MCQ')
    text = models.TextField()
    topic = models.CharField(max_length=100, blank=True, help_text='e.g. Algebra, Photosynthesis - for weak spot detection')
    marks = models.IntegerField(default=5)
    # MCQ fields
    option_a = models.CharField(max_length=500, blank=True)
    option_b = models.CharField(max_length=500, blank=True)
    option_c = models.CharField(max_length=500, blank=True)
    option_d = models.CharField(max_length=500, blank=True)
    correct_option = models.CharField(max_length=1, blank=True, choices=[('A','A'),('B','B'),('C','C'),('D','D')])
    # Subjective ideal answer
    ideal_answer = models.TextField(blank=True)
    keywords = models.TextField(blank=True, help_text='comma separated keywords for AI evaluation')
    
    def __str__(self):
        return f"Q{self.id} - {self.exam.title[:20]}"

class ExamSubmission(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)
    cancel_reason = models.CharField(max_length=200, blank=True)
    total_score = models.FloatField(default=0)
    percentage = models.FloatField(default=0)
    is_flagged_low = models.BooleanField(default=False)  # <70%
    
    class Meta:
        unique_together = ('exam','student')

class StudentAnswer(models.Model):
    submission = models.ForeignKey(ExamSubmission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1, blank=True)
    subjective_text = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True)
    score = models.FloatField(default=0)
    ai_feedback = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.submission.student.username} - Q{self.question.id}"
