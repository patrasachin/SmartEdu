import os
from django import forms
from django.conf import settings
from apps.accounts.forms import DeptSemForm
from apps.accounts.departments import teacher_departments
from .models import ALLOWED_EXTENSIONS


class MaterialForm(DeptSemForm):
    title = forms.CharField(max_length=200)
    subject = forms.CharField(max_length=100)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
    file = forms.FileField(required=False, label='File',
                           help_text='PDF, Word, PowerPoint, Excel, CSV or text. Up to %d MB.' % settings.MATERIAL_MAX_MB)
    link = forms.URLField(required=False, max_length=500, label='Link',
                          help_text='A web page or video, e.g. https://www.khanacademy.org/...')

    def __init__(self, *a, user=None, subject_default='', **kw):
        super().__init__(*a, allowed_departments=teacher_departments(user), **kw)
        profile = getattr(user, 'teacher_profile', None)
        if subject_default:
            self.fields['subject'].initial = subject_default
        if profile and profile.department in teacher_departments(user):
            self.fields['department'].initial = profile.department

    def clean_file(self):
        f = self.cleaned_data.get('file')
        if not f:
            return f
        ext = os.path.splitext(f.name)[1].lstrip('.').lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError('That file type is not allowed. Use: ' + ', '.join(ALLOWED_EXTENSIONS) + '.')
        if f.size > settings.MATERIAL_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f'File is too large. The limit is {settings.MATERIAL_MAX_MB} MB.')
        return f

    def clean(self):
        data = super().clean()
        if not data.get('file') and not data.get('link') and 'file' not in self.errors and 'link' not in self.errors:
            raise forms.ValidationError('Attach a file, paste a link, or both.')
        return data
