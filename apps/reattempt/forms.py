import os
from django import forms
from django.conf import settings
from django.utils import timezone

from apps.accounts.forms import StyledForm

PROOF_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']


class RequestForm(StyledForm):
    reason = forms.CharField(label='Why did you miss the exam?', widget=forms.Textarea(attrs={'rows': 4}), min_length=15,
                             error_messages={'min_length': 'Please explain in a little more detail (at least 15 characters).'})
    proof = forms.FileField(label='Supporting proof', help_text='For example a medical certificate or a letter. PDF, photo (JPG, PNG) or Word. Up to %d MB.' % settings.PROOF_MAX_MB)

    def clean_proof(self):
        f = self.cleaned_data['proof']
        ext = os.path.splitext(f.name)[1].lstrip('.').lower()
        if ext not in PROOF_EXTENSIONS:
            raise forms.ValidationError('That file type is not allowed. Use: ' + ', '.join(PROOF_EXTENSIONS) + '.')
        if f.size > settings.PROOF_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f'The file is too large. The limit is {settings.PROOF_MAX_MB} MB.')
        return f


class DecisionForm(StyledForm):
    action = forms.ChoiceField(choices=[('approve', 'Approve'), ('reject', 'Reject')])
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))
    extended_until = forms.DateTimeField(required=False, input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'])

    def clean(self):
        data = super().clean()
        if data.get('action') == 'approve':
            until = data.get('extended_until')
            if not until:
                self.add_error('extended_until', 'Choose until when the student may take the exam.')
            elif until <= timezone.now():
                self.add_error('extended_until', 'That time has already passed. Choose a future time.')
        elif data.get('action') == 'reject' and not (data.get('comment') or '').strip():
            self.add_error('comment', 'Please tell the student why the request was rejected.')
        return data
