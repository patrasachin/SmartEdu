import os
from django.db import models
from django.utils import timezone
from apps.accounts.models import User


def proof_path(instance, filename):
    return f'reattempt/{timezone.now():%Y/%m}/{filename}'


class ReattemptRequest(models.Model):
    """A student who missed an exam explains why, uploads proof, and the teacher decides."""
    STATUS = (('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'))
    exam = models.ForeignKey('exams.Exam', on_delete=models.CASCADE, related_name='reattempt_requests')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reattempt_requests')
    reason = models.TextField()
    proof = models.FileField(upload_to=proof_path)
    status = models.CharField(max_length=10, choices=STATUS, default='PENDING')
    teacher_comment = models.TextField(blank=True)
    extended_until = models.DateTimeField(null=True, blank=True)   # the personal deadline given to this student only
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exam', 'student')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.username} - {self.exam.title} ({self.status})'

    @property
    def proof_name(self):
        return os.path.basename(self.proof.name) if self.proof else ''

    @property
    def proof_ext(self):
        return os.path.splitext(self.proof.name)[1].lstrip('.').lower() if self.proof else ''

    @property
    def chance_is_open(self):
        return self.status == 'APPROVED' and self.extended_until is not None and self.extended_until > timezone.now()
