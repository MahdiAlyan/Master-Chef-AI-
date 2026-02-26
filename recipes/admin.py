from django.contrib import admin

from .models import Recipe, RecipeActivity, RecipeComment, RecipeShare, RecipeTag, RecipeViewEvent


@admin.register(RecipeTag)
class RecipeTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "created_at")


class RecipeShareInline(admin.TabularInline):
    model = RecipeShare
    extra = 0
    autocomplete_fields = ("shared_with", "invited_by")


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "cuisine_type", "preparation_time", "status", "is_public", "is_favorite")
    list_filter = ("status", "is_public", "is_favorite", "ai_generated", "cuisine_type")
    search_fields = ("name", "ingredients", "instructions", "created_by__username")
    autocomplete_fields = ("created_by",)
    inlines = (RecipeShareInline,)


@admin.register(RecipeShare)
class RecipeShareAdmin(admin.ModelAdmin):
    list_display = ("recipe", "shared_with", "invited_by", "permission", "created_at")
    list_filter = ("permission",)
    autocomplete_fields = ("recipe", "shared_with", "invited_by")


@admin.register(RecipeComment)
class RecipeCommentAdmin(admin.ModelAdmin):
    list_display = ("recipe", "author", "created_at")
    search_fields = ("recipe__name", "author__username", "body")
    autocomplete_fields = ("recipe", "author")


@admin.register(RecipeActivity)
class RecipeActivityAdmin(admin.ModelAdmin):
    list_display = ("recipe", "actor", "action", "created_at")
    list_filter = ("action",)
    autocomplete_fields = ("recipe", "actor")


@admin.register(RecipeViewEvent)
class RecipeViewEventAdmin(admin.ModelAdmin):
    list_display = ("recipe", "user", "viewed_at")
    autocomplete_fields = ("recipe", "user")
