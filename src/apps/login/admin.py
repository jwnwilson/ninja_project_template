from django.contrib import admin

from .models import EmailVerification, PasswordReset

admin.site.register(EmailVerification)
admin.site.register(PasswordReset)
