from django.urls import path

from . import views


app_name = "recipes"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("recipes/", views.RecipeListView.as_view(), name="recipe_list"),
    path("recipes/favorites/", views.FavoriteRecipeListView.as_view(), name="favorite_recipes"),
    path("recipes/to-try/", views.ToTryRecipeListView.as_view(), name="to_try_recipes"),
    path("recipes/made-before/", views.MadeBeforeRecipeListView.as_view(), name="made_before_recipes"),
    path("recipes/shared/", views.SharedRecipeListView.as_view(), name="shared_recipes"),
    path("recipes/new/", views.RecipeCreateView.as_view(), name="recipe_create"),
    path("recipes/<int:pk>/", views.RecipeDetailView.as_view(), name="recipe_detail"),
    path("recipes/<int:pk>/edit/", views.RecipeUpdateView.as_view(), name="recipe_update"),
    path("recipes/<int:pk>/delete/", views.RecipeDeleteView.as_view(), name="recipe_delete"),
    path("recipes/<int:pk>/favorite/", views.RecipeToggleFavoriteView.as_view(), name="recipe_toggle_favorite"),
    path("recipes/<int:pk>/status/", views.RecipeStatusUpdateView.as_view(), name="recipe_update_status"),
    path("recipes/<int:pk>/share/", views.RecipeShareView.as_view(), name="recipe_share"),
    path("recipes/<int:pk>/comment/", views.RecipeCommentCreateView.as_view(), name="recipe_comment"),
    path("recipes/<int:pk>/copy/", views.CopyRecipeView.as_view(), name="recipe_copy"),
    path("search/", views.RecipeSearchView.as_view(), name="search"),
    path("search/results/", views.RecipeSearchResultsView.as_view(), name="search_results"),
    path("public/", views.PublicRecipeListView.as_view(), name="public_list"),
    path("ai/tools/", views.AIToolsView.as_view(), name="ai_tools"),
    path("ai/generate/", views.AIRecipeGenerateRedirectView.as_view(), name="ai_generate"),
    path("recipes/<int:pk>/ai/substitutions/", views.AIIngredientSubstitutionView.as_view(), name="ai_substitutions"),
    path("recipes/<int:pk>/ai/nutrition/", views.AINutritionEstimateView.as_view(), name="ai_nutrition"),
    path("ai/recommendations/", views.AIRecommendationsView.as_view(), name="ai_recommendations"),
]
