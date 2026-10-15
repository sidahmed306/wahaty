"""Documentation Swagger : la connexion par jeton (JWT) de TRC, comme celle de simplejwt."""

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class ApprovedUserJWTScheme(SimpleJWTScheme):
    target_class = "accounts.authentication.ApprovedUserJWTAuthentication"
    name = "jwtAuth"
