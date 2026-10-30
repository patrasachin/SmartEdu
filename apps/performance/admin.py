from django.contrib import admin
from .models import PerformanceReport, WeakTopic, Recommendation
admin.site.register(PerformanceReport)
admin.site.register(WeakTopic)
admin.site.register(Recommendation)
