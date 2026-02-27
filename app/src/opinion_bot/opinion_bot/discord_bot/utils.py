from django.conf import settings

_OPINION_SLUG_BASE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def create_user_mention(user_id: int) -> str:
    return f"<@{user_id}>"


def create_masked_opinion_url(opinion_id: int) -> str:
    slug = f"#{opinion_id:05d}"
    return f"[{slug}](<{settings.OPINION_DETAILS_URL}{opinion_id}>)"
