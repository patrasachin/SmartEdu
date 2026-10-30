import os
from django import forms
from django.conf import settings
from django.utils import timezone

from apps.accounts.departments import teacher_departments
from apps.accounts.forms import DeptSemForm, StyledForm
from .models import ALLOWED_EXTENSIONS


class AssignmentForm(DeptSemForm):
    title = forms.CharField(max_length=200, label='Assignment topic')
    subject = forms.CharField(max_length=100)
    due_date = forms.DateTimeField(required=False, label='Submit before', input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'],
                                   widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
                                   help_text='Optional. Late work is still accepted but marked late.')
    description = forms.CharField(required=False, label='Note for students', widget=forms.Textarea(attrs={'rows': 2}),
                                  help_text='Optional. The topic is enough.')

    def __init__(self, *a, user=None, subject_default='', **kw):
        super().__init__(*a, allowed_departments=teacher_departments(user), **kw)
        if subject_default:
            self.fields['subject'].initial = subject_default
        profile = getattr(user, 'teacher_profile', None)
        if profile and profile.department in teacher_departments(user):
            self.fields['department'].initial = profile.department


class SubmitForm(StyledForm):
    file = forms.FileField(label='Your work', help_text='PDF, Word, PowerPoint, Excel, text, or a photo (JPG, PNG). Up to %d MB.' % settings.ASSIGNMENT_MAX_MB)
    note = forms.CharField(required=False, label='Note to your teacher', widget=forms.Textarea(attrs={'rows': 2}))

    def clean_file(self):
        f = self.cleaned_data['file']
        ext = os.path.splitext(f.name)[1].lstrip('.').lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError('That file type is not allowed. Use: ' + ', '.join(ALLOWED_EXTENSIONS) + '.')
        if f.size > settings.ASSIGNMENT_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f'The file is too large. The limit is {settings.ASSIGNMENT_MAX_MB} MB.')
        return f


class ReviewForm(StyledForm):
    rating = forms.TypedChoiceField(choices=[(i, str(i)) for i in range(1, 6)], coerce=int, widget=forms.RadioSelect,
                                    error_messages={'required': 'Choose a rating from 1 to 5.'})
    review = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Review for the student')

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields['rating'].widget.attrs['class'] = 'form-check-input'
