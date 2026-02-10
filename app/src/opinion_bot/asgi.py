import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

# init django before importing urls
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "opinion_bot.settings")
http_app = get_asgi_application()

from .urls import ws_urlpatterns  # noqa


application = ProtocolTypeRouter(
    {
        "http": http_app,
        "websocket": URLRouter(ws_urlpatterns),
    }
)
