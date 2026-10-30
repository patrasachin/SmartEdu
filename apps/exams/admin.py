from django.contrib import admin
from .models import Exam, Question, ExamSubmission, StudentAnswer


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'department', 'status', 'scheduled_at', 'created_by']
    list_filter = ['status', 'department']


admin.site.register(Question)
admin.site.register(ExamSubmission)
admin.site.register(StudentAnswer)
