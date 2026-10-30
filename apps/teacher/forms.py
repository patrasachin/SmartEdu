from django import forms
from apps.accounts.departments import teacher_departments, semester_label, check_pair
from apps.accounts.forms import StyledModelForm
from apps.exams.models import Exam, Question

LOCAL_DT = '%Y-%m-%dT%H:%M'


class ExamForm(StyledModelForm):
    department = forms.ChoiceField(label='Department')
    semester = forms.ChoiceField(label='Semester')
    scheduled_at = forms.DateTimeField(
        label='Opens at', input_formats=[LOCAL_DT, '%Y-%m-%d %H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=LOCAL_DT))
    closes_at = forms.DateTimeField(
        label='Closes at', input_formats=[LOCAL_DT, '%Y-%m-%d %H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=LOCAL_DT),
        help_text='The last moment a student can start. Students who miss it can send a reason and proof to ask for another chance.')

    class Meta:
        model = Exam
        fields = ['title', 'subject', 'department', 'semester', 'description', 'duration_minutes', 'scheduled_at', 'closes_at']
        labels = {'duration_minutes': 'Duration (minutes)'}
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *a, user=None, **kw):
        super().__init__(*a, **kw)
        depts = teacher_departments(user) if user is not None else teacher_departments(None)
        self.fields['department'].choices = [('', 'Select a department')] + [(d, d) for d in depts]
        self.fields['semester'].choices = [('', 'Select a semester')] + [(str(i), semester_label(i)) for i in range(1, 9)]
        profile = getattr(user, 'teacher_profile', None)
        if not self.is_bound and not self.instance.pk and profile and profile.department in depts:
            self.fields['department'].initial = profile.department      # a sensible default: the teacher's own department

    def clean(self):
        data = super().clean()
        dept, sem = data.get('department'), data.get('semester')
        if dept and sem:
            err = check_pair(dept, sem)
            if err:
                self.add_error('semester', err)
            else:
                data['semester'] = int(sem)
        start, end = data.get('scheduled_at'), data.get('closes_at')
        if start and end and end <= start:
            self.add_error('closes_at', 'The closing time must be after the opening time.')
        return data

    def clean_duration_minutes(self):
        d = self.cleaned_data['duration_minutes']
        if not 1 <= d <= 600:
            raise forms.ValidationError('Enter a duration between 1 and 600 minutes.')
        return d


class QuestionForm(StyledModelForm):
    class Meta:
        model = Question
        fields = ['qtype', 'topic', 'text', 'marks', 'option_a', 'option_b', 'option_c', 'option_d',
                  'correct_option', 'ideal_answer', 'keywords']
        labels = {'qtype': 'Type', 'text': 'Question', 'option_a': 'Option A', 'option_b': 'Option B',
                  'option_c': 'Option C', 'option_d': 'Option D', 'correct_option': 'Correct option',
                  'ideal_answer': 'Ideal answer', 'keywords': 'Keywords'}
        widgets = {'text': forms.Textarea(attrs={'rows': 2}), 'ideal_answer': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'topic': 'Used to find weak topics, e.g. Algebra.',
                      'keywords': 'Comma separated, e.g. symbols, equation, variable',
                      'ideal_answer': 'The AI compares written answers with this.'}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields['topic'].required = True
        self.fields['correct_option'].choices = [('', 'Choose')] + list(Question._meta.get_field('correct_option').choices)

    def clean_marks(self):
        m = self.cleaned_data['marks']
        if m < 1:
            raise forms.ValidationError('Marks must be at least 1.')
        return m

    def clean(self):
        data = super().clean()
        if data.get('qtype') == 'MCQ':
            for k in ('option_a', 'option_b', 'option_c', 'option_d'):
                if not (data.get(k) or '').strip():
                    self.add_error(k, 'Fill in all four options.')
            if not data.get('correct_option'):
                self.add_error('correct_option', 'Choose the correct option.')
            data['ideal_answer'], data['keywords'] = '', ''
        elif data.get('qtype') == 'SUBJECTIVE':
            if not (data.get('ideal_answer') or '').strip() and not (data.get('keywords') or '').strip():
                self.add_error('ideal_answer', 'Add an ideal answer or keywords so the AI can score this.')
            for k in ('option_a', 'option_b', 'option_c', 'option_d', 'correct_option'):
                data[k] = ''
        return data
