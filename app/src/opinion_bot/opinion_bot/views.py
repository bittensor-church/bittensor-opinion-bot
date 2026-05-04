import logging
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect

logger = logging.getLogger(__name__)


def redirect_to_grafana_opinions(request: HttpRequest) -> HttpResponseRedirect:
    """
    Redirect rules:

    - /opinions/id=<opinion_id> -> OPINION_DETAILS_REDIRECT_URL?var-opinion_id=<opinion_id>
    - /opinions/channel_id=<channel_id> -> OPINIONS_REDIRECT_URL?var-channel=id<channel_id>
    - /opinions -> OPINIONS_REDIRECT_URL

    If both id and channel_id are present, id takes precedence.
    """
    opinion_id = request.GET.get("id")
    channel_id = request.GET.get("channel_id")

    logger.debug(f"Redirecting to dashboard with opinion_id: {opinion_id}, channel_id: {channel_id}")

    if opinion_id:
        query = urlencode({"var-opinion_id": opinion_id})
        return HttpResponseRedirect(f"{settings.OPINION_DETAILS_REDIRECT_URL}?{query}")

    if channel_id:
        query = urlencode({"var-channel": channel_id})
        return HttpResponseRedirect(f"{settings.OPINIONS_REDIRECT_URL}?{query}")

    return HttpResponseRedirect(settings.OPINIONS_REDIRECT_URL)
