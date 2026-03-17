from django.db import models


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


class SubnetInstance(models.Model):
    """
    Subnet instances managed manually by the admin.
    """

    name = models.CharField(
        max_length=255,
        help_text="Human readable subnet instance name",
    )
    netuid = models.PositiveIntegerField()
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subnet Instance"
        verbose_name_plural = "Subnet Instances"
        indexes = [
            models.Index(fields=["is_archived", "netuid"]),
        ]

    def __str__(self) -> str:
        archived = " [ARCHIVED]" if self.is_archived else ""
        return f"#{self.id} → Subnet {self.netuid} {self.name}{archived}"


class Opinion(models.Model):
    """
    An opinion about a subnet.

    VISIBILITY:
    - FEATURED: shown publicly (key role or significant participant)
    - HIDDEN: stored but not shown (regular user)

    STATUS:
    - PENDING: FEATURED opinion not yet posted to Discord
    - VALID: valid opinion (FEATURED posted to Discord or HIDDEN) and not yet replaced
    - REPLACED: replaced by another opinion from the same user for the same subnet instance
    """

    class Visibility(models.TextChoices):
        FEATURED = "featured", "Featured"
        HIDDEN = "hidden", "Hidden"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VALID = "valid", "Valid"
        REPLACED = "replaced", "Replaced"

    subnet_instance = models.ForeignKey(
        SubnetInstance,
        on_delete=models.RESTRICT,
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
            models.Index(fields=["subnet_instance", "visibility", "status", "created_at"]),
            models.Index(fields=["subnet_instance", "author", "status", "created_at"]),
            models.Index(fields=["message_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.emoji} by {self.author} on subnet {self.subnet_instance.netuid}"


class Upvote(models.Model):
    """
    An opinion upvote.

    VISIBILITY:
    - FEATURED: shown publicly (key role or significant participant)
    - HIDDEN: stored but not shown (regular user)

    STATUS:
    - VALID: valid upvote (not yet moved to another opinion)
    - REPLACED: replaced by another upvote from the same user for an opinion for the same subnet instance
    """

    class Visibility(models.TextChoices):
        FEATURED = "featured", "Featured"
        HIDDEN = "hidden", "Hidden"

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        REPLACED = "replaced", "Replaced"

    # Subnet Instance
    subnet_instance = models.ForeignKey(
        SubnetInstance,
        on_delete=models.RESTRICT,
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
        on_delete=models.RESTRICT,
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
            models.Index(fields=["subnet_instance", "visibility", "status", "created_at"]),
            models.Index(fields=["subnet_instance", "author", "status"]),
        ]

    def __str__(self) -> str:
        return f"Upvote for opinion {self.opinion_id} on subnet {self.subnet_instance.netuid}"
