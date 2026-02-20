_OPINION_SLUG_BASE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def create_user_mention(user_id: int) -> str:
    return f"<@{user_id}>"


def create_opinion_slug(opinion_id: int) -> str:
    digits = []
    n = opinion_id
    base = len(_OPINION_SLUG_BASE_CHARS)
    while n:
        digits.append(_OPINION_SLUG_BASE_CHARS[n % base])
        n //= base

    return ''.join(reversed(digits)).zfill(4)
