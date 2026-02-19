from constance import config

def is_user_important(user_role_ids: set[int]) -> bool:
    important_role_ids_str = config.IMPORTANT_ROLE_IDS # FIXME: why ide complains "Unresolved const"
    important_role_ids = set([int(id_str) for id_str in important_role_ids_str.split(",")])
    return bool(user_role_ids.intersection(important_role_ids))