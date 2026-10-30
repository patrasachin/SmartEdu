from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme

from apps.notifications.models import Notification
from .forms import LoginForm, StyledPasswordChangeForm, ForgotPasswordForm
from .models import User

ROLE_HOME = {
    'ADMIN': '/admin-portal/dashboard/',
    'TEACHER': '/teacher/dashboard/',
    'STUDENT': '/student/dashboard/',
}

DEMO_ACCOUNTS = [
    ('Admin', 'admin', 'admin123'),
    ('Teacher', 'teacher1', 'teacher123'),
    ('Student', 'student1', 'student123'),
]


def role_home(user):
    return ROLE_HOME.get(user.role, '/auth/login/')


def home_redirect(request):
    """Signed-out visitors see the landing page; signed-in users go to their portal."""
    if not request.user.is_authenticated:
        return render(request, 'landing.html')
    return redirect(role_home(request.user))


def login_view(request):
    if request.user.is_authenticated:
        return redirect(role_home(request.user))
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
        if user is None:
            messages.error(request, 'Wrong username or password. Check both and try again.')
        elif not user.is_active:
            messages.error(request, 'This account is switched off. Ask your admin to turn it back on.')
        else:
            login(request, user)
            nxt = request.POST.get('next') or request.GET.get('next')
            if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
                return redirect(nxt)
            return redirect(role_home(user))
    ctx = {'form': form, 'next': request.GET.get('next', ''),
           'demo_accounts': DEMO_ACCOUNTS if settings.DEBUG else []}
    return render(request, 'auth/login.html', ctx)


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('/auth/login/')


def register_view(request):
    return render(request, 'auth/register.html')


def forgot_password(request):
    form = ForgotPasswordForm(request.POST or None)
    sent = False
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        note = form.cleaned_data['note']
        # Same answer whether or not the username exists, so usernames can't be probed.
        if User.objects.filter(username=username).exists():
            Notification.objects.bulk_create([
                Notification(recipient=a, title='Password reset requested',
                             message=f'{username} asked for a password reset. {note}'.strip(), ntype='GENERAL')
                for a in User.objects.filter(role='ADMIN', is_active=True)
            ])
        sent = True
    return render(request, 'auth/forgot_password.html', {'form': form, 'sent': sent})


@login_required
def change_password(request):
    form = StyledPasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Password changed.')
        return redirect(role_home(user))
    return render(request, 'auth/change_password.html', {'form': form})
