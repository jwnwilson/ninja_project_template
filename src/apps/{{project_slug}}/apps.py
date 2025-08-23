from django.apps import AppConfig


class {{project_slug|capitalize}}Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.{{project_slug}}"
