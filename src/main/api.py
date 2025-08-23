from ninja.security import SessionAuth
from ninja_extra import NinjaExtraAPI
from ninja_jwt.authentication import JWTAuth

from apps.{{project_slug}}.api import router as {{project_slug}}_router
from apps.{{project_slug}}.controllers import {{project_slug|capitalize}}Controller
from apps.login.controllers.login import NinjaJWTController, SignupController

api = NinjaExtraAPI(
    title="AI Pet API",
    description="AI Pet",
    urls_namespace="{{project_slug}}",
    auth=[SessionAuth(), JWTAuth()],
)

api.register_controllers(NinjaJWTController)
api.register_controllers({{project_slug|capitalize}}Controller)
api.register_controllers(SignupController)
api.add_router("{{project_slug}}", {{project_slug}}_router)
