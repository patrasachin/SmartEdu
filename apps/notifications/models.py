from django.db import models
from apps.accounts.models import User

class Notification(models.Model):
    TYPE = (('EXAM','Exam'),('ATTENDANCE','Attendance'),('RESULT','Result'),('ASSIGNMENT','Assignment'),('REATTEMPT','Re-attempt'),('GENERAL','General'))
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    ntype = models.CharField(max_length=20, choices=TYPE, default='GENERAL')
    is_read = models.BooleanField(default=False)
    related_exam = models.ForeignKey('exams.Exam', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"To {self.recipient.username}: {self.title}"



class EmailLog(models.Model):
    """One row for every email SmartEdu tries to send to a guardian, so admins can see what went out."""
    KIND = (('RESULT', 'Exam result'), ('ATTENDANCE', 'Attendance'), ('CANCELLED', 'Exam cancelled'), ('TEST', 'Test'))
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='guardian_emails')
    to_email = models.EmailField()
    subject = models.CharField(max_length=250)
    body = models.TextField()
    kind = models.CharField(max_length=20, choices=KIND)
    key = models.CharField(max_length=120, blank=True, db_index=True)   # used to avoid sending the same email twice
    status = models.CharField(max_length=10, default='SENT')            # SENT or FAILED
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.kind} to {self.to_email} ({self.status})"
