from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .departments import department_choices, semester_label, check_pair
from .models import User, StudentProfile, TeacherProfile


class BootstrapMixin:
    """Adds Bootstrap classes to every widget."""
    def _style(self):
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs['class'] = 'form-check-input'
            elif isinstance(w, forms.Select):
                w.attrs['class'] = 'form-select'
            else:
                w.attrs['class'] = (w.attrs.get('class', '') + ' form-control').strip()


class StyledForm(BootstrapMixin, forms.Form):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class StyledModelForm(BootstrapMixin, forms.ModelForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class StyledPasswordChangeForm(BootstrapMixin, PasswordChangeForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class LoginForm(StyledForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


class PersonForm(StyledForm):
    """Shared fields for registering a student or a teacher."""
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=False)
    password = forms.CharField(required=False, help_text='Leave blank to generate one.')

    def clean_username(self):
        u = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError('That username is already taken.')
        return u


class DeptSemForm(StyledForm):
    """Two linked drop-downs: department, then semester (8 semesters, or 4 for MBA and MCA)."""
    department = forms.ChoiceField(label='Department')
    semester = forms.ChoiceField(label='Semester', help_text='8 semesters for every department except MBA and MCA, which have 4.')

    def __init__(self, *a, allowed_departments=None, **kw):
        super().__init__(*a, **kw)
        depts = allowed_departments or department_choices()
        self.fields['department'].choices = [('', 'Select a department')] + [(d, d) for d in depts]
        self.fields['semester'].choices = [('', 'Select a semester')] + [(str(i), semester_label(i)) for i in range(1, 9)]

    def clean(self):
        data = super().clean()
        dept, sem = data.get('department'), data.get('semester')
        if dept and sem and 'department' not in self.errors and 'semester' not in self.errors:
            err = check_pair(dept, sem)
            if err:
                self.add_error('semester', err)
            else:
                data['semester'] = int(sem)
        return data


class StudentRegisterForm(PersonForm, DeptSemForm):
    roll_number = forms.CharField(max_length=20)
    guardian_name = forms.CharField(max_length=100, label="Guardian's name")
    guardian_email = forms.EmailField(label="Guardian's email",
                                      help_text='Exam results and attendance are emailed here. Required.',
                                      error_messages={'required': "The guardian's email is required."})

    def clean_roll_number(self):
        r = self.cleaned_data['roll_number'].strip()
        if StudentProfile.objects.filter(roll_number__iexact=r).exists():
            raise forms.ValidationError('That roll number already exists.')
        return r


class StudentEditForm(DeptSemForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    guardian_name = forms.CharField(max_length=100, label="Guardian's name")
    guardian_email = forms.EmailField(label="Guardian's email", error_messages={'required': "The guardian's email is required."})


class TeacherRegisterForm(PersonForm):
    employee_id = forms.CharField(max_length=20)
    subject = forms.CharField(max_length=100)
    department = forms.ChoiceField(label='Department')

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields['department'].choices = [('', 'Select a department')] + [(d, d) for d in department_choices()]

    def clean_employee_id(self):
        e = self.cleaned_data['employee_id'].strip()
        if TeacherProfile.objects.filter(employee_id__iexact=e).exists():
            raise forms.ValidationError('That employee ID already exists.')
        return e


class TeacherEditForm(StyledForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    employee_id = forms.CharField(max_length=20)
    subject = forms.CharField(max_length=100)
    department = forms.ChoiceField(label='Department')

    def __init__(self, *a, teacher=None, **kw):
        super().__init__(*a, **kw)
        self.teacher = teacher
        choices = [('', 'Select a department')] + [(d, d) for d in department_choices()]
        current = getattr(getattr(teacher, 'teacher_profile', None), 'department', '')
        if current and current not in department_choices():     # an old value from before the fixed list: keep it selectable
            choices.append((current, current + ' (old value)'))
        self.fields['department'].choices = choices

    def clean_employee_id(self):
        e = self.cleaned_data['employee_id'].strip()
        qs = TeacherProfile.objects.filter(employee_id__iexact=e)
        if self.teacher is not None:
            qs = qs.exclude(user=self.teacher)
        if qs.exists():
            raise forms.ValidationError('That employee ID already exists.')
        return e


class ForgotPasswordForm(StyledForm):
    username = forms.CharField(max_length=150, label='Your username')
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), label='Anything the admin should know (optional)')
