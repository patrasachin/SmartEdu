from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from .models import Notification


@login_required
def notification_list(request):
    notifs = list(Notification.objects.filter(recipient=request.user).select_related('sender', 'related_exam').order_by('-created_at')[:100])
    unread_ids = [n.id for n in notifs if not n.is_read]
    # `n.is_read` stays as it was for this render so new items are highlighted; they are marked read afterwards.
    Notification.objects.filter(id__in=unread_ids).update(is_read=True)
    return render(request, 'notifications/list.html', {'notifications': notifs, 'unread_count': len(unread_ids)})


@login_required
@require_POST
def mark_read(request, notif_id):
    Notification.objects.filter(id=notif_id, recipient=request.user).update(is_read=True)
    return JsonResponse({'ok': True})


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notification_list')
