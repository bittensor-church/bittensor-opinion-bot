from django.conf import settings


def create_user_mention(user_id: int) -> str:
    return f"<@{user_id}>"


def create_masked_opinion_url(opinion_id: int) -> str:
    slug = f"#{opinion_id:05d}"
    return f"[{slug}](<{settings.OPINIONS_URL}/?id={opinion_id}>)"
