"""Delete uploaded files when the database row that owns them is deleted (for example when an admin deletes a
student or a teacher, which also removes their submissions, proofs and shared material)."""
from django.db.models.signals import post_delete
from django.dispatch import receiver


def _remove(field_file):
    try:
        if field_file and field_file.name:
            field_file.storage.delete(field_file.name)
    except Exception:       # a missing file must never block a delete
        pass


def connect():
    from apps.assignments.models import AssignmentSubmission
    from apps.materials.models import StudyMaterial
    from apps.proctoring.models import ProctoringLog
    from apps.reattempt.models import ReattemptRequest

    @receiver(post_delete, sender=AssignmentSubmission, weak=False, dispatch_uid='smartedu_del_submission_file')
    def _submission(sender, instance, **kw):
        _remove(instance.file)

    @receiver(post_delete, sender=ReattemptRequest, weak=False, dispatch_uid='smartedu_del_proof_file')
    def _proof(sender, instance, **kw):
        _remove(instance.proof)

    @receiver(post_delete, sender=ProctoringLog, weak=False, dispatch_uid='smartedu_del_snapshot_file')
    def _snapshot(sender, instance, **kw):
        _remove(instance.image_snapshot)

    @receiver(post_delete, sender=StudyMaterial, weak=False, dispatch_uid='smartedu_del_material_file')
    def _material(sender, instance, **kw):
        # one stored file may be shared by several rows: remove it only when the last row is gone
        if instance.file and not StudyMaterial.objects.filter(file=instance.file.name).exists():
            _remove(instance.file)
