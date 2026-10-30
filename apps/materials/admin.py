from django.contrib import admin
from .models import StudyMaterial


@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'department', 'uploaded_by', 'created_at']
    list_filter = ['department', 'subject']
