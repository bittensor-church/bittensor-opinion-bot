from django.conf import settings
from django.contrib.admin.sites import site
from django.http import HttpResponse
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .api.routers import router as api_router
from .opinion_bot.business_metrics import metrics_manager
from .opinion_bot.consumers import DefaultConsumer
from .opinion_bot.metrics import metrics_view

urlpatterns = [
    path("alive/", lambda _: HttpResponse(b"ok")),
    path("admin/", site.urls),
    re_path(r"^api/(?P<version>v0)/", include(api_router.urls)),
    re_path(r"^api/(?P<version>v0)/schema/$", SpectacularAPIView.as_view(), name="schema"),
    re_path(r"^api/(?P<version>v0)/schema/swagger-ui/$", SpectacularSwaggerView.as_view(url_name="schema")),
    re_path(r"^api/auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("metrics", metrics_view, name="prometheus-django-metrics"),
    path("business-metrics", metrics_manager.view, name="prometheus-business-metrics"),
    path("", include("django.contrib.auth.urls")),
]

ws_urlpatterns = [
    path("ws/v0/", DefaultConsumer.as_asgi()),
]

if settings.DEBUG_TOOLBAR:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
    ]
