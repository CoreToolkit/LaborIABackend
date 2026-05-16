from types import SimpleNamespace

from core.config import settings

try:
    from authlib.integrations.starlette_client import OAuth  # type: ignore
except ImportError:  # pragma: no cover - fallback for test env without authlib installed
    class OAuth:
        def __init__(self):
            self._apps = {}

        def register(self, name: str, **kwargs):
            app = SimpleNamespace(
                authorize_redirect=None,
                authorize_access_token=None,
                parse_id_token=None,
                get=None,
                **kwargs,
            )
            self._apps[name] = app
            setattr(self, name, app)
            return app

oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

oauth.register(
    name="microsoft",
    client_id=settings.MICROSOFT_CLIENT_ID,
    client_secret=settings.MICROSOFT_CLIENT_SECRET,
    server_metadata_url=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/v2.0/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)
