import os
from django.db import models
from django.utils import timezone
from apps.accounts.models import User

# extension -> (label, bootstrap icon, css class)
KINDS = {
    'pdf': ('PDF', 'bi-file-earmark-pdf', 'fk-pdf'),
    'doc': ('Word', 'bi-file-earmark-word', 'fk-word'),
    'docx': ('Word', 'bi-file-earmark-word', 'fk-word'),
    'ppt': ('PowerPoint', 'bi-file-earmark-ppt', 'fk-ppt'),
    'pptx': ('PowerPoint', 'bi-file-earmark-ppt', 'fk-ppt'),
    'xls': ('Excel', 'bi-file-earmark-excel', 'fk-excel'),
    'xlsx': ('Excel', 'bi-file-earmark-excel', 'fk-excel'),
    'csv': ('Excel', 'bi-file-earmark-excel', 'fk-excel'),
    'txt': ('Text', 'bi-file-earmark-text', 'fk-text'),
}
ALLOWED_EXTENSIONS = sorted(KINDS)
LINK_KIND = ('Link', 'bi-link-45deg', 'fk-link')


def material_path(instance, filename):
    return f'materials/{timezone.now():%Y/%m}/{filename}'


class StudyMaterial(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=100)
    department = models.CharField('Department', max_length=100, db_index=True)
    semester = models.PositiveSmallIntegerField('Semester', default=1)
    file = models.FileField(upload_to=material_path, blank=True)
    link = models.URLField(max_length=500, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='materials')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.department}, semester {self.semester})'

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def extension(self):
        return os.path.splitext(self.file.name)[1].lstrip('.').lower() if self.file else ''

    @property
    def _kind(self):
        return KINDS.get(self.extension, ('File', 'bi-file-earmark', 'fk-text')) if self.file else LINK_KIND

    @property
    def kind_label(self):
        return self._kind[0]

    @property
    def icon(self):
        return self._kind[1]

    @property
    def css(self):
        return self._kind[2]

    @property
    def size_display(self):
        try:
            n = self.file.size
        except (OSError, ValueError):
            return ''
        return f'{n / 1024:.0f} KB' if n < 1024 * 1024 else f'{n / 1024 / 1024:.1f} MB'
