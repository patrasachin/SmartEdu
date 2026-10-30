from django import forms
from apps.accounts.departments import department_choices, semester_label, check_pair
from apps.accounts.forms import StyledForm


class AnnouncementForm(StyledForm):
    AUDIENCE = [('ALL', 'Everyone'), ('STUDENT', 'All students'), ('TEACHER', 'All teachers'), ('DEPT', 'One department (and semester)')]
    audience = forms.ChoiceField(choices=AUDIENCE)
    department = forms.ChoiceField(required=False, label='Department', help_text='Only used for "One department"')
    semester = forms.ChoiceField(required=False, label='Semester')
    title = forms.CharField(max_length=200)
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields['department'].choices = [('', 'Select a department')] + [(d, d) for d in department_choices()]
        self.fields['semester'].choices = [('', 'All semesters')] + [(str(i), semester_label(i)) for i in range(1, 9)]

    def clean(self):
        data = super().clean()
        if data.get('audience') == 'DEPT':
            if not data.get('department'):
                self.add_error('department', 'Choose the department.')
            elif data.get('semester'):
                err = check_pair(data['department'], data['semester'])
                if err:
                    self.add_error('semester', err)
            data['semester'] = int(data['semester']) if data.get('semester') and not self.errors else None
        return data
