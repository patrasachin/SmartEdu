from django.db import models
from apps.accounts.models import User

class ProctoringLog(models.Model):
    VIOLATION_TYPES = (
        ('TAB_SWITCH','Tab Switch / Browser Exit'),
        ('FULLSCREEN_EXIT','Fullscreen Exit'),
        ('NO_FACE','No Face Detected'),
        ('MULTIPLE_FACE','Multiple Faces'),
        ('NO_MIC','Mic Disabled'),
        ('COPY_PASTE','Copy Paste Attempt'),
    )
    submission = models.ForeignKey('exams.ExamSubmission', on_delete=models.CASCADE, related_name='proctoring_logs')
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    violation_type = models.CharField(max_length=30, choices=VIOLATION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    image_snapshot = models.ImageField(upload_to='proctoring/', null=True, blank=True)
    details = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.violation_type} at {self.timestamp}"
