from django.db import models
from apps.accounts.models import User

class PerformanceReport(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='performance_reports')
    exam = models.ForeignKey('exams.Exam', on_delete=models.CASCADE, null=True)
    total_marks = models.FloatField()
    obtained_marks = models.FloatField()
    percentage = models.FloatField()
    understanding_level = models.CharField(max_length=50)  # Excellent, Good, Average, Weak
    generated_at = models.DateTimeField(auto_now_add=True)
    ai_summary = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.percentage}%"

class WeakTopic(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='weak_topics')
    topic = models.CharField(max_length=100)
    subject = models.CharField(max_length=100)
    failure_count = models.IntegerField(default=1)
    avg_score_in_topic = models.FloatField(default=0)
    last_detected = models.DateTimeField(auto_now=True)
    is_improved = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('student','topic','subject')
    
    def __str__(self):
        return f"{self.student.username} weak in {self.topic}"

class Recommendation(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendations')
    topic = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    resource_link = models.URLField(blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
