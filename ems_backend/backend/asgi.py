"""
ASGI config for backend project.

Routes HTTP requests to Django and WebSocket requests to Channels consumers.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialise Django before importing things that touch the ORM/models.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler  # noqa: E402

from lt_panels.routing import websocket_urlpatterns as lt_panels_ws  # noqa: E402
from assets.routing import websocket_urlpatterns as assets_ws  # noqa: E402

# Daphne runs the ASGI app directly (not runserver), so wrap the HTTP app to
# serve /static/ from the staticfiles finders — otherwise admin/Jazzmin assets 404.
application = ProtocolTypeRouter({
    'http': ASGIStaticFilesHandler(django_asgi_app),
    'websocket': AuthMiddlewareStack(URLRouter(lt_panels_ws + assets_ws)),
})
