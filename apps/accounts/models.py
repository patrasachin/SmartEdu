from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('TEACHER', 'Teacher'),
        ('STUDENT', 'Student'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='STUDENT')
    phone = models.CharField(max_length=20, blank=True)
    profile_pic = models.ImageField(upload_to='profiles/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.username} ({self.role})"

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    roll_number = models.CharField(max_length=20, unique=True)
    department = models.CharField('Department', max_length=100, default='')
    semester = models.PositiveSmallIntegerField('Semester', default=1)   # 1 to 8 (1 to 4 for MBA and MCA)
    guardian_name = models.CharField(max_length=100, blank=True)
    guardian_email = models.EmailField(blank=True)   # results and attendance are emailed here
    admission_date = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.roll_number} - {self.user.get_full_name()}"

class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    subject = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name()}"
