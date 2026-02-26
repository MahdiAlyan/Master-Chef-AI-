from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView, TemplateView

from services import gemini_service
from services.gemini_service import GeminiServiceError

from .forms import AIMealPlannerForm, AIRecipeGenerateForm, RecipeCommentForm, RecipeForm, ShareRecipeForm
from .models import Recipe, RecipeActivity, RecipeComment, RecipeShare, RecipeTag, RecipeViewEvent


def _recipe_queryset():
    return (
        Recipe.objects.select_related("created_by")
        .prefetch_related("tags", "shares__shared_with")
        .annotate(comment_count=Count("comments", distinct=True))
    )


def _visible_queryset(user):
    return _recipe_queryset().filter(Q(created_by=user) | Q(is_public=True) | Q(shares__shared_with=user)).distinct()


def _owner_queryset(user):
    return _recipe_queryset().filter(created_by=user)


def _log_activity(recipe: Recipe, actor, action: str, description: str = ""):
    RecipeActivity.objects.create(recipe=recipe, actor=actor, action=action, description=description)


def _invalidate_dashboard_cache(user_ids: Iterable[int]):
    for user_id in user_ids:
        cache.delete(f"dashboard_stats:{user_id}")
        cache.delete(f"dashboard_ai:{user_id}")


def _apply_recipe_filters(qs, request: HttpRequest):
    q = request.GET.get("q", "").strip()
    ingredient = request.GET.get("ingredient", "").strip()
    cuisine = request.GET.get("cuisine", "").strip()
    max_prep = request.GET.get("max_prep", "").strip()
    status = request.GET.get("status", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(ingredients__icontains=q) | Q(instructions__icontains=q))
    if ingredient:
        qs = qs.filter(ingredients__icontains=ingredient)
    if cuisine:
        qs = qs.filter(cuisine_type__icontains=cuisine)
    if max_prep.isdigit():
        qs = qs.filter(preparation_time__lte=int(max_prep))
    if status == "favorite":
        qs = qs.filter(is_favorite=True)
    elif status in {Recipe.STATUS_TO_TRY, Recipe.STATUS_MADE_BEFORE}:
        qs = qs.filter(status=status)

    sort_map = {
        "newest": "-created_at",
        "oldest": "created_at",
        "prep": "preparation_time",
        "alpha": "name",
    }
    return qs.order_by(sort_map.get(sort, "-created_at"))


def _filter_query_string(request: HttpRequest):
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    if encoded:
        return f"{encoded}&"
    return ""


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "recipes/dashboard.html"

    def _stats(self):
        key = f"dashboard_stats:{self.request.user.id}"
        cached = cache.get(key)
        if cached:
            return cached

        recipes = Recipe.objects.filter(created_by=self.request.user)
        stats = {
            "total_recipes": recipes.count(),
            "favorite_count": recipes.filter(is_favorite=True).count(),
            "to_try_count": recipes.filter(status=Recipe.STATUS_TO_TRY).count(),
            "made_before_count": recipes.filter(status=Recipe.STATUS_MADE_BEFORE).count(),
            "shared_with_others_count": RecipeShare.objects.filter(invited_by=self.request.user).count(),
            "shared_with_me_count": RecipeShare.objects.filter(shared_with=self.request.user).count(),
        }
        cache.set(key, stats, timeout=300)
        return stats

    def _recently_viewed(self):
        events = (
            RecipeViewEvent.objects.filter(user=self.request.user)
            .select_related("recipe", "recipe__created_by")
            .order_by("-viewed_at")[:24]
        )
        deduped = OrderedDict()
        for event in events:
            deduped[event.recipe_id] = event.recipe
            if len(deduped) >= 6:
                break
        return list(deduped.values())

    def _ai_suggestions(self):
        key = f"dashboard_ai:{self.request.user.id}"
        cached = cache.get(key)
        if cached:
            return cached

        recipes = Recipe.objects.filter(created_by=self.request.user).only("name", "preparation_time", "ingredients")
        favorites = recipes.filter(is_favorite=True)[:10]
        titles = list(recipes.values_list("name", flat=True)[:100])
        favorite_titles = list(favorites.values_list("name", flat=True))

        suggestions = {"based_on_favorites": [], "quick_meals": [], "healthy_options": []}
        try:
            if titles:
                suggestions["based_on_favorites"] = gemini_service.recommend_recipes(
                    user_context=f"Favorites: {', '.join(favorite_titles) or 'none'}",
                    candidate_titles=titles,
                )
        except GeminiServiceError:
            suggestions["based_on_favorites"] = favorite_titles[:4]

        suggestions["quick_meals"] = list(
            Recipe.objects.filter(created_by=self.request.user, preparation_time__gt=0, preparation_time__lte=30).values_list(
                "name", flat=True
            )[:4]
        )
        suggestions["healthy_options"] = list(
            Recipe.objects.filter(
                created_by=self.request.user,
            )
            .filter(
                Q(name__icontains="healthy")
                | Q(name__icontains="salad")
                | Q(ingredients__icontains="vegetable")
                | Q(ingredients__icontains="olive oil")
            )
            .values_list("name", flat=True)[:4]
        )
        cache.set(key, suggestions, timeout=1800)
        return suggestions

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        stats = self._stats()
        ctx.update(stats)
        ctx["recent_recipes"] = _owner_queryset(self.request.user).order_by("-created_at")[:8]
        ctx["recently_viewed"] = self._recently_viewed()
        ctx["ai_suggestions"] = self._ai_suggestions()
        return ctx


class RecipeListView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = "recipes/recipe_list.html"
    context_object_name = "recipes"
    paginate_by = 12
    list_mode = "my"

    def get_queryset(self):
        if self.list_mode == "shared":
            qs = _recipe_queryset().filter(shares__shared_with=self.request.user).exclude(created_by=self.request.user).distinct()
        elif self.list_mode == "favorites":
            qs = _owner_queryset(self.request.user).filter(is_favorite=True)
        elif self.list_mode == "to_try":
            qs = _owner_queryset(self.request.user).filter(status=Recipe.STATUS_TO_TRY)
        elif self.list_mode == "made_before":
            qs = _owner_queryset(self.request.user).filter(status=Recipe.STATUS_MADE_BEFORE)
        else:
            qs = _owner_queryset(self.request.user)
        return _apply_recipe_filters(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        titles = {
            "my": "My Recipes",
            "shared": "Shared Recipes",
            "favorites": "Favorites",
            "to_try": "To Try",
            "made_before": "Made Before",
        }
        ctx["list_mode"] = self.list_mode
        ctx["list_title"] = titles.get(self.list_mode, "Recipes")
        ctx["tags"] = RecipeTag.objects.all()[:100]
        ctx["filter_query"] = _filter_query_string(self.request)
        return ctx


class FavoriteRecipeListView(RecipeListView):
    list_mode = "favorites"


class ToTryRecipeListView(RecipeListView):
    list_mode = "to_try"


class MadeBeforeRecipeListView(RecipeListView):
    list_mode = "made_before"


class SharedRecipeListView(RecipeListView):
    list_mode = "shared"


class PublicRecipeListView(ListView):
    model = Recipe
    template_name = "recipes/public_list.html"
    context_object_name = "recipes"
    paginate_by = 12

    def get_queryset(self):
        return _apply_recipe_filters(_recipe_queryset().filter(is_public=True), self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_query"] = _filter_query_string(self.request)
        return ctx


class RecipeAccessMixin(LoginRequiredMixin):
    def get_queryset(self):
        return _visible_queryset(self.request.user).prefetch_related(
            Prefetch("comments", queryset=RecipeComment.objects.select_related("author")),
            Prefetch("activities", queryset=RecipeActivity.objects.select_related("actor")),
        )


class RecipeEditMixin(RecipeAccessMixin):
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if not obj.can_edit(self.request.user):
            raise Http404
        return obj


class RecipeDetailView(RecipeAccessMixin, DetailView):
    model = Recipe
    template_name = "recipes/recipe_detail.html"
    context_object_name = "recipe"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if not obj.can_view(self.request.user):
            raise Http404
        RecipeViewEvent.objects.create(recipe=obj, user=self.request.user)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.object.pk
        ctx["can_edit"] = self.object.can_edit(self.request.user)
        ctx["can_share"] = self.object.created_by_id == self.request.user.id
        ctx["share_form"] = ShareRecipeForm(request_user=self.request.user)
        ctx["comment_form"] = RecipeCommentForm()
        ctx["subs"] = self.request.session.get(f"subs_{pk}", [])
        ctx["nutrition"] = self.request.session.get(f"nutrition_{pk}", {})
        ctx["shares"] = self.object.shares.select_related("shared_with")
        return ctx


class RecipeCreateView(LoginRequiredMixin, TemplateView):
    template_name = "recipes/recipe_form.html"

    def get(self, request: HttpRequest, *args, **kwargs):
        form = RecipeForm()
        return render(
            request,
            self.template_name,
            {"form": form, "tags": RecipeTag.objects.values_list("name", flat=True)[:100], "page_title": "Add Recipe"},
        )

    def post(self, request: HttpRequest, *args, **kwargs):
        form = RecipeForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"form": form, "tags": RecipeTag.objects.values_list("name", flat=True)[:100], "page_title": "Add Recipe"},
            )
        recipe = form.save(commit=False)
        recipe.created_by = request.user
        recipe.save()
        form.instance = recipe
        form.save_m2m()
        _log_activity(recipe, request.user, RecipeActivity.ACTION_CREATED, "Recipe created")
        _invalidate_dashboard_cache([request.user.id])
        messages.success(request, "Recipe created.")
        return redirect("recipes:recipe_detail", pk=recipe.pk)


class RecipeUpdateView(RecipeEditMixin, TemplateView):
    template_name = "recipes/recipe_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.recipe = get_object_or_404(_visible_queryset(request.user), pk=kwargs["pk"])
        if not self.recipe.can_edit(request.user):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, *args, **kwargs):
        form = RecipeForm(instance=self.recipe)
        return render(
            request,
            self.template_name,
            {"form": form, "recipe": self.recipe, "tags": RecipeTag.objects.values_list("name", flat=True)[:100], "page_title": "Edit Recipe"},
        )

    def post(self, request: HttpRequest, *args, **kwargs):
        form = RecipeForm(request.POST, request.FILES, instance=self.recipe)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"form": form, "recipe": self.recipe, "tags": RecipeTag.objects.values_list("name", flat=True)[:100], "page_title": "Edit Recipe"},
            )
        recipe = form.save()
        _log_activity(recipe, request.user, RecipeActivity.ACTION_UPDATED, "Recipe updated")
        _invalidate_dashboard_cache([request.user.id, recipe.created_by_id])
        messages.success(request, "Recipe updated.")
        return redirect("recipes:recipe_detail", pk=recipe.pk)


class RecipeDeleteView(LoginRequiredMixin, DeleteView):
    model = Recipe
    template_name = "recipes/recipe_confirm_delete.html"
    success_url = reverse_lazy("recipes:recipe_list")

    def get_queryset(self):
        return _owner_queryset(self.request.user)

    def delete(self, request, *args, **kwargs):
        recipe = self.get_object()
        owner_id = recipe.created_by_id
        share_user_ids = list(recipe.shares.values_list("shared_with_id", flat=True))
        _log_activity(recipe, request.user, RecipeActivity.ACTION_UPDATED, "Recipe deleted")
        messages.success(request, "Recipe deleted.")
        response = super().delete(request, *args, **kwargs)
        _invalidate_dashboard_cache([owner_id, *share_user_ids])
        return response


class RecipeToggleFavoriteView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        recipe = get_object_or_404(_visible_queryset(request.user), pk=pk)
        if not recipe.can_edit(request.user):
            raise Http404
        recipe.is_favorite = not recipe.is_favorite
        recipe.save(update_fields=["is_favorite", "updated_at"])
        _log_activity(
            recipe,
            request.user,
            RecipeActivity.ACTION_FAVORITE,
            f"Favorite set to {'on' if recipe.is_favorite else 'off'}",
        )
        _invalidate_dashboard_cache([recipe.created_by_id, request.user.id])
        messages.success(request, "Favorite updated.")
        return redirect(request.POST.get("next") or reverse("recipes:recipe_detail", kwargs={"pk": pk}))


class RecipeStatusUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        recipe = get_object_or_404(_visible_queryset(request.user), pk=pk)
        if not recipe.can_edit(request.user):
            raise Http404
        status = request.POST.get("status", "").strip()
        if status in {Recipe.STATUS_TO_TRY, Recipe.STATUS_MADE_BEFORE}:
            recipe.status = status
            recipe.save(update_fields=["status", "updated_at"])
            _log_activity(recipe, request.user, RecipeActivity.ACTION_STATUS, f"Status changed to {status}")
            _invalidate_dashboard_cache([recipe.created_by_id, request.user.id])
            messages.success(request, "Status updated.")
        return redirect(request.POST.get("next") or reverse("recipes:recipe_detail", kwargs={"pk": pk}))


class RecipeShareView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        recipe = get_object_or_404(_owner_queryset(request.user), pk=pk)
        form = ShareRecipeForm(request.POST, request_user=request.user)
        if not form.is_valid():
            messages.error(request, form.errors.get("__all__") or form.errors.get("target") or "Could not share recipe.")
            return redirect("recipes:recipe_detail", pk=pk)

        target_user = form.cleaned_data["target_user"]
        permission = form.cleaned_data["permission"]
        share, created = RecipeShare.objects.update_or_create(
            recipe=recipe,
            shared_with=target_user,
            defaults={"permission": permission, "invited_by": request.user},
        )
        verb = "invited" if created else "updated permissions for"
        _log_activity(recipe, request.user, RecipeActivity.ACTION_SHARED, f"{verb} {target_user.username}")
        _invalidate_dashboard_cache([request.user.id, target_user.id])
        messages.success(request, f"Recipe shared with {target_user.username}.")
        return redirect("recipes:recipe_detail", pk=pk)


class RecipeCommentCreateView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        recipe = get_object_or_404(_visible_queryset(request.user), pk=pk)
        if not recipe.can_view(request.user):
            raise Http404
        form = RecipeCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.recipe = recipe
            comment.author = request.user
            comment.save()
            _log_activity(recipe, request.user, RecipeActivity.ACTION_COMMENTED, "Added a comment")
            messages.success(request, "Comment added.")
        else:
            messages.error(request, "Comment cannot be empty.")
        return redirect(f"{reverse('recipes:recipe_detail', kwargs={'pk': pk})}#comments")


class CopyRecipeView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        recipe = Recipe.objects.filter(pk=pk, is_public=True).select_related("created_by").first()
        if not recipe:
            raise Http404
        if recipe.created_by_id == request.user.id:
            messages.info(request, "This recipe is already in your collection.")
            return redirect("recipes:recipe_detail", pk=recipe.pk)

        new_recipe = Recipe.objects.create(
            name=recipe.name,
            description=recipe.description,
            ingredients=recipe.ingredients,
            instructions=recipe.instructions,
            cuisine_type=recipe.cuisine_type,
            preparation_time=recipe.preparation_time,
            difficulty_level=recipe.difficulty_level,
            servings=recipe.servings,
            created_by=request.user,
            is_favorite=False,
            status=Recipe.STATUS_TO_TRY,
            ai_generated=recipe.ai_generated,
            is_public=False,
        )
        new_recipe.tags.set(recipe.tags.all())
        _log_activity(new_recipe, request.user, RecipeActivity.ACTION_CREATED, "Copied from public recipe")
        _invalidate_dashboard_cache([request.user.id])
        messages.success(request, "Recipe copied to your collection.")
        return redirect("recipes:recipe_detail", pk=new_recipe.pk)


class RecipeSearchView(LoginRequiredMixin, TemplateView):
    template_name = "recipes/search.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tags"] = RecipeTag.objects.values_list("name", flat=True)[:100]
        ctx["results_url"] = reverse("recipes:search_results")
        return ctx


class RecipeSearchResultsView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = "recipes/partials/search_results.html"
    context_object_name = "recipes"
    paginate_by = 12

    def get_queryset(self):
        qs = _visible_queryset(self.request.user)
        return _apply_recipe_filters(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_query"] = self.request.GET.get("q", "").strip()
        ctx["filter_query"] = _filter_query_string(self.request)
        return ctx


class AIToolsView(LoginRequiredMixin, TemplateView):
    template_name = "recipes/ai_generate.html"

    def _base_context(self):
        return {
            "generate_form": AIRecipeGenerateForm(),
            "meal_form": AIMealPlannerForm(),
            "generated_recipe": None,
            "meal_plan": None,
            "recommendations": [],
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self._base_context())
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        ctx = self._base_context()

        if action == "generate_recipe":
            form = AIRecipeGenerateForm(request.POST)
            ctx["generate_form"] = form
            if form.is_valid():
                try:
                    ctx["generated_recipe"] = gemini_service.generate_recipe(
                        available_ingredients=form.cleaned_data["available_ingredients"],
                        cuisine_type=form.cleaned_data.get("cuisine_type", ""),
                        dietary_restriction=form.cleaned_data.get("dietary_restriction", ""),
                        max_prep_time=form.cleaned_data.get("max_prep_time"),
                    )
                    messages.success(request, "AI recipe generated.")
                except GeminiServiceError as e:
                    messages.error(request, str(e))
            return render(request, self.template_name, ctx)

        if action == "save_generated":
            title = request.POST.get("title", "").strip()
            ingredients = request.POST.get("ingredients", "").strip()
            instructions = request.POST.get("instructions", "").strip()
            description = request.POST.get("description", "").strip()
            cuisine_type = request.POST.get("cuisine_type", "").strip()
            prep_time = request.POST.get("prep_time", "0").strip()
            servings = request.POST.get("servings", "2").strip()
            if not title or not ingredients or not instructions:
                messages.error(request, "Generated recipe is incomplete.")
                return redirect("recipes:ai_tools")
            try:
                prep_time_val = max(int(prep_time), 0)
            except ValueError:
                prep_time_val = 0
            try:
                servings_val = max(int(servings), 1)
            except ValueError:
                servings_val = 2
            recipe = Recipe.objects.create(
                name=title,
                description=description,
                ingredients=ingredients,
                instructions=instructions,
                cuisine_type=cuisine_type,
                preparation_time=prep_time_val,
                servings=servings_val,
                created_by=request.user,
                status=Recipe.STATUS_TO_TRY,
                ai_generated=True,
            )
            _log_activity(recipe, request.user, RecipeActivity.ACTION_AI, "Saved AI-generated recipe")
            _invalidate_dashboard_cache([request.user.id])
            messages.success(request, "AI recipe saved to your collection.")
            return redirect("recipes:recipe_detail", pk=recipe.pk)

        if action == "meal_plan":
            form = AIMealPlannerForm(request.POST)
            ctx["meal_form"] = form
            if form.is_valid():
                favorites = list(
                    Recipe.objects.filter(created_by=request.user, is_favorite=True).values_list("name", flat=True)[:20]
                )
                pantry = list(
                    Recipe.objects.filter(created_by=request.user).values_list("ingredients", flat=True)[:20]
                )
                try:
                    ctx["meal_plan"] = gemini_service.generate_meal_plan(
                        favorites=favorites,
                        pantry_ingredients=pantry,
                        days=form.cleaned_data["days"],
                        max_prep_time=form.cleaned_data.get("max_prep_time"),
                        dietary_restriction=form.cleaned_data.get("dietary_restriction", ""),
                    )
                    messages.success(request, "Weekly meal plan generated.")
                except GeminiServiceError as e:
                    messages.error(request, str(e))
            return render(request, self.template_name, ctx)

        return redirect("recipes:ai_tools")


class AIIngredientSubstitutionView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        recipe = get_object_or_404(_visible_queryset(request.user), pk=pk)
        if not recipe.can_view(request.user):
            raise Http404
        try:
            subs = gemini_service.suggest_substitutions(recipe.ingredients)
        except GeminiServiceError as e:
            messages.error(request, str(e))
            return redirect("recipes:recipe_detail", pk=pk)
        request.session[f"subs_{pk}"] = subs
        _log_activity(recipe, request.user, RecipeActivity.ACTION_AI, "Generated ingredient substitutions")
        messages.success(request, "Substitution suggestions generated.")
        return redirect("recipes:recipe_detail", pk=pk)


class AINutritionEstimateView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        recipe = get_object_or_404(_visible_queryset(request.user), pk=pk)
        if not recipe.can_view(request.user):
            raise Http404
        try:
            nutrition = gemini_service.estimate_nutrition(recipe.ingredients)
        except GeminiServiceError as e:
            messages.error(request, str(e))
            return redirect("recipes:recipe_detail", pk=pk)
        request.session[f"nutrition_{pk}"] = nutrition
        _log_activity(recipe, request.user, RecipeActivity.ACTION_AI, "Generated nutrition estimate")
        messages.success(request, "Nutrition estimate generated.")
        return redirect("recipes:recipe_detail", pk=pk)


class AIRecommendationsView(LoginRequiredMixin, TemplateView):
    template_name = "recipes/ai_recommendations.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        favorites = Recipe.objects.filter(created_by=self.request.user, is_favorite=True)[:20]
        all_titles = list(Recipe.objects.filter(created_by=self.request.user).values_list("name", flat=True)[:100])
        user_context = "Favorites: " + ", ".join([r.name for r in favorites])
        try:
            recommended = gemini_service.recommend_recipes(user_context=user_context, candidate_titles=all_titles)
            ctx["recommended"] = recommended
        except GeminiServiceError as e:
            ctx["error"] = str(e)
            ctx["recommended"] = []
        return ctx


class AIRecipeGenerateRedirectView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect("recipes:ai_tools")


class SharedRecipeRedirectView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect("recipes:shared_recipes")
