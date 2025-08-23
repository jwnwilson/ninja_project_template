from django.contrib import admin

from .models.{{project_slug}} import {{project_slug|capitalize}}


# Register your models here.
class {{project_slug|capitalize}}Admin(admin.ModelAdmin):
    pass


admin.site.register({{project_slug|capitalize}}, {{project_slug|capitalize}}Admin)
