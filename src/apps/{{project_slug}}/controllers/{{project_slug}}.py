from django.contrib.auth import get_user_model
from ninja import ModelSchema
from ninja_extra import (
    ModelConfig,
    ModelControllerBase,
    ModelSchemaConfig,
    api_controller,
)
from ninja_extra.permissions import BasePermission, IsAuthenticated

from ..models import {{project_slug|capitalize}}


class PetSchema(ModelSchema):
    class Config:
        model = {{project_slug|capitalize}}
        model_fields = ["name", "description"]


class IsAdmin(BasePermission):
    def has_permission(self, request, controller):
        return request.user.is_staff


@api_controller("/{{project_slug}}", permissions=[IsAuthenticated, IsAdmin], tags=["{{project_slug|capitalize}}"])
class {{project_slug|capitalize}}Controller(ModelControllerBase):
    user_model = get_user_model()
    model_config = ModelConfig(
        model={{project_slug|capitalize}},
        schema_config=ModelSchemaConfig(
            read_only_fields=["id", "created_at", "updated_at"]
        ),
    )
