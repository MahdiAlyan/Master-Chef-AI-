from django.conf import settings
from django.db import models


class RecipeTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Recipe(models.Model):
    STATUS_TO_TRY = "to_try"
    STATUS_MADE_BEFORE = "made_before"

    STATUS_CHOICES = [
        (STATUS_TO_TRY, "To try"),
        (STATUS_MADE_BEFORE, "Made before"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    ingredients = models.TextField()
    instructions = models.TextField()
    cuisine_type = models.CharField(max_length=100, blank=True)
    preparation_time = models.IntegerField(default=0)
    difficulty_level = models.CharField(max_length=50, blank=True)
    servings = models.PositiveIntegerField(default=2)
    image = models.ImageField(upload_to="recipes/", blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipes")
    tags = models.ManyToManyField(RecipeTag, blank=True, related_name="recipes")
    is_favorite = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TO_TRY)
    ai_generated = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def can_edit(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.created_by_id == user.id:
            return True
        return self.shares.filter(shared_with=user, permission=RecipeShare.PERMISSION_EDIT).exists()

    def can_view(self, user):
        if self.is_public:
            return True
        if not user or not user.is_authenticated:
            return False
        if self.created_by_id == user.id:
            return True
        return self.shares.filter(shared_with=user).exists()


class RecipeShare(models.Model):
    PERMISSION_VIEW = "view"
    PERMISSION_EDIT = "edit"
    PERMISSION_CHOICES = [
        (PERMISSION_VIEW, "View only"),
        (PERMISSION_EDIT, "Can edit"),
    ]

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="shares")
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_recipe_shares",
    )
    shared_with = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_recipes",
    )
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default=PERMISSION_VIEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("recipe", "shared_with")]

    def __str__(self):
        return f"{self.recipe.name} -> {self.shared_with.username} ({self.permission})"


class RecipeComment(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipe_comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author} on {self.recipe}"


class RecipeActivity(models.Model):
    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_SHARED = "shared"
    ACTION_COMMENTED = "commented"
    ACTION_FAVORITE = "favorite"
    ACTION_STATUS = "status"
    ACTION_AI = "ai"

    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_SHARED, "Shared"),
        (ACTION_COMMENTED, "Commented"),
        (ACTION_FAVORITE, "Favorite changed"),
        (ACTION_STATUS, "Status changed"),
        (ACTION_AI, "AI tool used"),
    ]

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipe_activities",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipe} - {self.action}"


class RecipeViewEvent(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="view_events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipe_views")
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-viewed_at"]

    def __str__(self):
        return f"{self.user} viewed {self.recipe}"
