from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, TemplateView

from .forms import (
    AccountDeleteForm,
    ProfileUpdateForm,
    SignUpForm,
    StyledAuthenticationForm,
    StyledPasswordChangeForm,
    ThemePreferenceForm,
)


User = get_user_model()


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Account created. You can now log in.")
        return response


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = StyledAuthenticationForm


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["owned_recipe_count"] = user.recipes.count()
        ctx["shared_recipe_count"] = user.shared_recipes.count()
        return ctx


class PublicProfileView(DetailView):
    model = User
    template_name = "accounts/public_profile.html"
    slug_field = "username"
    slug_url_kwarg = "username"

    def get_queryset(self):
        return User.objects.filter(Q(is_active=True))


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profile_form"] = kwargs.get("profile_form") or ProfileUpdateForm(instance=self.request.user)
        ctx["password_form"] = kwargs.get("password_form") or StyledPasswordChangeForm(user=self.request.user)
        ctx["theme_form"] = kwargs.get("theme_form") or ThemePreferenceForm(initial={"theme": "system"})
        ctx["delete_form"] = kwargs.get("delete_form") or AccountDeleteForm()
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "profile":
            profile_form = ProfileUpdateForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated.")
                return redirect("accounts:settings")
            return render(
                request,
                self.template_name,
                self.get_context_data(profile_form=profile_form),
            )

        if action == "password":
            password_form = StyledPasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed.")
                return redirect("accounts:settings")
            return render(
                request,
                self.template_name,
                self.get_context_data(password_form=password_form),
            )

        if action == "theme":
            theme_form = ThemePreferenceForm(request.POST)
            if theme_form.is_valid():
                request.session["theme_preference"] = theme_form.cleaned_data["theme"]
                messages.success(request, "Theme preference updated.")
                return redirect("accounts:settings")
            return render(
                request,
                self.template_name,
                self.get_context_data(theme_form=theme_form),
            )

        if action == "delete":
            delete_form = AccountDeleteForm(request.POST)
            if delete_form.is_valid():
                request.user.delete()
                messages.success(request, "Account deleted.")
                return redirect("accounts:signup")
            return render(
                request,
                self.template_name,
                self.get_context_data(delete_form=delete_form),
            )

        return redirect("accounts:settings")
