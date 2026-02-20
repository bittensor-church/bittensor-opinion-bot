from django.contrib import admin  # noqa
from django.contrib.admin import register  # noqa

from opinion_bot.opinion_bot.models import DiscordChannel, DiscordRole

admin.site.site_header = "opinion_bot Administration"
admin.site.site_title = "opinion_bot"
admin.site.index_title = "Welcome to opinion_bot Administration"


@admin.register(DiscordRole)
class DiscordRoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "is_key_role", "updated_at")
    list_filter = ("is_key_role",)
    search_fields = ("id", "name", "slug")
    ordering = ("-is_key_role", "slug", "name", "id")
    readonly_fields = ("updated_at",)
    list_editable = ("name", "slug", "is_key_role")

@admin.register(DiscordChannel)
class DiscordChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "netuid", "is_archived", "updated_at")
    list_filter = ("is_archived", "netuid")
    search_fields = ("id", "name")
    ordering = ("netuid", "is_archived", "name", "id")
    readonly_fields = ("updated_at",)
    list_editable = ("name", "netuid", "is_archived")

