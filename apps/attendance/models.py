from django.db import models
from apps.accounts.models import User

class Attendance(models.Model):
    STATUS = (('PRESENT','Present'),('ABSENT','Absent'),('LATE','Late'))
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS, default='PRESENT')
    department = models.CharField(max_length=100)
    semester = models.PositiveSmallIntegerField(default=1)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marked_attendances')
    remarks = models.CharField(max_length=200, blank=True)
    
    class Meta:
        unique_together = ('student','date')
    
    def __str__(self):
        return f"{self.student.username} - {self.date} - {self.status}"
