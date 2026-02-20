from django.db import models


class SubnetInstance(models.Model):
    """
    A subnet registration instance, keyed by (netuid, registration_block).

    IMMUTABLE:
    - Once created, subnet instances are not updated
    - Ownership changes (coldkey swaps) are tracked separately, not here

    WHY VERSIONED:
    - Subnets can be deregistered and re-registered on the same netuid
    - Each registration is a NEW instance to avoid mixing old/new opinions
    - Only one instance per netuid should be active at a time

    LIFECYCLE:
    - Created when a new subnet is registered (from Sentinel API)
    - deregistration_block set when subnet deregisters (instance becomes inactive)
    - Old opinions remain linked to the old instance (archived)
    """

    netuid = models.PositiveIntegerField(db_index=True)
    name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Human-readable subnet name",
    )
    registration_block = models.PositiveBigIntegerField(
        help_text="Block number when this subnet was registered",
    )
    deregistration_block = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="Block number when deregistered (null = still active)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["netuid", "registration_block"]
        verbose_name = "Subnet Instance"
        verbose_name_plural = "Subnet Instances"

    def __str__(self) -> str:
        status = "active" if self.is_active else "archived"
        return f"Subnet {self.netuid} (block {self.registration_block}) - {status}"

    @property
    def is_active(self) -> bool:
        """Subnet is active if it hasn't been deregistered."""
        return self.deregistration_block is None


class DiscordUser(models.Model):
    """
    A Discord user with their current username/display name.

    IDENTITY:
    - Primary key IS the Discord snowflake ID (bigint)
    - No auto-increment ID needed

    NAMING:
    - username: Global Discord username (e.g., "alice")
    - display_name: Per-guild display name (nick), updated on each interaction
    - Only the LATEST values are stored (updated when user submits opinion)

    USAGE:
    - Created/updated automatically when user submits an opinion
    - Referenced by Opinion.author and Opinion.annotator
    """

    id = models.BigIntegerField(
        primary_key=True,
        help_text="Discord user snowflake ID",
    )
    username = models.CharField(
        max_length=255,
        help_text="Global Discord username",
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Per-guild display name (nick), may differ from username",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Discord User"
        verbose_name_plural = "Discord Users"

    def __str__(self) -> str:
        if self.display_name and self.display_name != self.username:
            return f"{self.display_name} (@{self.username})"
        return f"@{self.username}"


class DiscordRole(models.Model):
    """
    Discord roles with key role designation for filtering.

    KEY ROLES:
    - Roles marked as key_role=True are used in queries
    - Examples: subnet_owner, validator, founder, moderator, otf
    - Used to filter/enrich opinions in the key_roles view

    ADMIN USAGE:
    - Add roles from Discord server
    - Mark important roles as key_role=True
    - slug is used in API filters
    """

    id = models.BigIntegerField(
        primary_key=True,
        help_text="Discord role snowflake ID",
    )
    name = models.CharField(
        max_length=255,
        help_text="Role name from Discord",
    )
    slug = models.SlugField(
        max_length=64,
        unique=True,
        help_text="URL-safe identifier for API filtering",
    )
    is_key_role = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Key roles used in queries (subnet_owner, validator, founder, etc.)",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Discord Role"
        verbose_name_plural = "Discord Roles"

    def __str__(self) -> str:
        key = " [KEY]" if self.is_key_role else ""
        return f"{self.name} ({self.slug}){key}"

class UserRole(models.Model):
    """
    Many-to-many relationship between users and roles.

    UPDATED ON EACH INTERACTION:
    - When user submits opinion, their current roles are synced
    - Old roles removed, new roles added
    """

    user = models.ForeignKey(
        DiscordUser,
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    role = models.ForeignKey(
        DiscordRole,
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "role"]
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"

    def __str__(self) -> str:
        return f"{self.user} has {self.role}"


class DiscordChannel(models.Model):
    """
    Discord channels with their subnets netuids

    ARCHIVING:
    - is_archived=True hides channel from default views
    - Archived channels can be shown optionally in queries

    ADMIN USAGE:
    - Create one mapping per subnet channel in Discord
    - Set is_archived=True when channel is no longer active
    """

    id = models.BigIntegerField(
        primary_key=True,
        help_text="Discord channel snowflake ID",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Channel name (for admin display)",
    )
    netuid = models.PositiveIntegerField(
        db_index=True,
        help_text="Subnet netuid this channel is mapped to",
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Archived channels hidden by default",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Discord Channel"
        verbose_name_plural = "Discord Channels"

    def __str__(self) -> str:
        archived = " [ARCHIVED]" if self.is_archived else ""
        return f"#{self.name or self.id} → Subnet {self.netuid}{archived}"


class Opinion(models.Model):
    """
    An opinion about a subnet.

    VISIBILITY:
    - FEATURED: shown publicly (key role or significant participant)
    - HIDDEN: stored but not shown (regular user)

    STATUS:
    - PENDING: FEATURED opinion not yet posted to Discord
    - VALID: valid opinion (FEATURED posted to Discord or HIDDEN) and not yet replaced
    - REPLACED: replaced by another opinion from the same user in the same channel
    """

    class Visibility(models.TextChoices):
        FEATURED = "featured", "Featured"
        HIDDEN = "hidden", "Hidden"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VALID = "valid", "Valid"
        REPLACED = "replaced", "Replaced"

    # Channel
    channel = models.ForeignKey(
        DiscordChannel,
        on_delete=models.CASCADE,
        related_name="opinions",
    )

    # Author
    author = models.ForeignKey(
        DiscordUser,
        on_delete=models.CASCADE,
        related_name="authored_opinions",
        help_text="User who submitted the opinion",
    )

    # Content
    emoji = models.CharField(
        max_length=64,
        help_text="Emoji representing the opinion sentiment",
    )
    content = models.TextField(
        help_text="The opinion text content",
    )

    # Discord message ID if posted (for FEATURED opinions)
    message_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Discord message ID",
    )

    # Visibility
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.HIDDEN,
        db_index=True,
    )

    # Status
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Opinion"
        verbose_name_plural = "Opinions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "visibility", "status", "created_at"]),
            models.Index(fields=["channel", "author", "status", "created_at"]),
            models.Index(fields=["message_id"]), # FIXME: migration
        ]

    def __str__(self) -> str:
        return f"{self.emoji} by {self.author} on channel {self.channel.id}"


class Upvote(models.Model):
    """
    An opinion upvote.

    VISIBILITY:
    - FEATURED: shown publicly (key role or significant participant)
    - HIDDEN: stored but not shown (regular user)

    STATUS:
    - VALID: valid upvote (not yet moved to another opinion)
    - REPLACED: replaced by another upvote from the same user in the same channel
    """

    class Visibility(models.TextChoices):
        FEATURED = "featured", "Featured"
        HIDDEN = "hidden", "Hidden"

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        REPLACED = "replaced", "Replaced"

    # Channel
    channel = models.ForeignKey(
        DiscordChannel,
        on_delete=models.CASCADE,
        related_name="upvotes",
    )

    # Author
    author = models.ForeignKey(
        DiscordUser,
        on_delete=models.CASCADE,
        related_name="authored_upvotes",
        help_text="User who upvoted the opinion",
    )

    # Opinion
    opinion = models.ForeignKey(
        Opinion,
        on_delete=models.CASCADE,
        related_name="upvoted_opinions",
        help_text="Upvoted opinion",
    )

    # Visibility
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.HIDDEN,
        db_index=True,
    )

    # Status
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.VALID,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Upvote"
        verbose_name_plural = "Upvotes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "visibility", "status", "created_at"]),
            models.Index(fields=["channel", "author", "status"]),
        ]

    def __str__(self) -> str:
        return f"Upvote for opinion {self.opinion_id} on channel {self.channel.id}"
