from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'age', 'gender', 'phone_number', 'created_at']
    list_filter = ['gender', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']
