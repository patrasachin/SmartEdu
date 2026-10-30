import os
from django.db import models
from django.utils import timezone
from apps.accounts.models import User

# allowed uploads: documents and photos
ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'jpg', 'jpeg', 'png']
IMAGE_EXTENSIONS = ('jpg', 'jpeg', 'png')
KINDS = {
    'pdf': ('PDF', 'bi-file-earmark-pdf', 'fk-pdf'), 'doc': ('Word', 'bi-file-earmark-word', 'fk-word'),
    'docx': ('Word', 'bi-file-earmark-word', 'fk-word'), 'ppt': ('PowerPoint', 'bi-file-earmark-ppt', 'fk-ppt'),
    'pptx': ('PowerPoint', 'bi-file-earmark-ppt', 'fk-ppt'), 'xls': ('Excel', 'bi-file-earmark-excel', 'fk-excel'),
    'xlsx': ('Excel', 'bi-file-earmark-excel', 'fk-excel'), 'txt': ('Text', 'bi-file-earmark-text', 'fk-text'),
    'jpg': ('Photo', 'bi-file-earmark-image', 'fk-link'), 'jpeg': ('Photo', 'bi-file-earmark-image', 'fk-link'),
    'png': ('Photo', 'bi-file-earmark-image', 'fk-link'),
}


def submission_path(instance, filename):
    return f'assignments/{timezone.now():%Y/%m}/{filename}'


class Assignment(models.Model):
    """The teacher sends only a topic (plus an optional note and due date) to a department and semester."""
    title = models.CharField('Topic', max_length=200)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=100)
    department = models.CharField('Department', max_length=100, db_index=True)
    semester = models.PositiveSmallIntegerField('Semester', default=1)
    due_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.department}, semester {self.semester})'

    @property
    def is_overdue(self):
        return bool(self.due_date and timezone.now() > self.due_date)


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_submissions')
    file = models.FileField(upload_to=submission_path)
    note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_late = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)        # 1 to 5 stars, set by the teacher
    review = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('assignment', 'student')
        ordering = ['-submitted_at']

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def extension(self):
        return os.path.splitext(self.file.name)[1].lstrip('.').lower() if self.file else ''

    @property
    def kind(self):
        return KINDS.get(self.extension, ('File', 'bi-file-earmark', 'fk-text'))

    @property
    def is_image(self):
        return self.extension in IMAGE_EXTENSIONS

    @property
    def is_reviewed(self):
        return self.rating is not None

    @property
    def star_range(self):
        return range(1, 6)
