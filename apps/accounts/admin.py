from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, StudentProfile, TeacherProfile


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'is_active', 'is_verified']
    list_filter = ['role', 'is_active']
    fieldsets = UserAdmin.fieldsets + (('Role Info', {'fields': ('role', 'phone', 'profile_pic', 'is_verified')}),)
    add_fieldsets = UserAdmin.add_fieldsets + ((None, {'fields': ('role',)}),)


admin.site.register(StudentProfile)
admin.site.register(TeacherProfile)
