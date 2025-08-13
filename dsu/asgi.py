"""
ASGI config for dsu project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""
import os
from django.core.asgi import get_asgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsu.settings')
# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

import django
from channels.routing import ProtocolTypeRouter,URLRouter
from channels.auth import AuthMiddlewareStack
from channels.sessions import SessionMiddlewareStack
from api.jwt_middleware import JWTAuthMiddleware
import live.routing
import bills.routing
import api.routing
django.setup()

application = ProtocolTypeRouter({
    "https":get_asgi_application(),
    "websocket":SessionMiddlewareStack(
        JWTAuthMiddleware(
            URLRouter([
                # More specific patterns first to avoid conflicts
                *api.routing.websocket_urlpatterns,
                *bills.routing.websocket_urlpatterns,
                *live.routing.websocket_urlpatterns,
            ])
        )
    )
})

