from django.db import models

from apps.core.models import BaseModel


class {{project_slug|capitalize}}(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name
