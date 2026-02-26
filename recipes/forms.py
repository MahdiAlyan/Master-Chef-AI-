import re

from django import forms
from django.contrib.auth import get_user_model

from .models import Recipe, RecipeComment, RecipeShare, RecipeTag


User = get_user_model()


def _apply_styles(form):
    base = "w-full rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/80"
    for field in form.fields.values():
        if isinstance(field.widget, forms.HiddenInput):
            continue
        existing = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = (existing + " " + base).strip()


def parse_ingredient_line(line: str):
    text = (line or "").strip()
    if not text:
        return {"quantity": "", "unit": "", "name": ""}
    match = re.match(r"^\s*([0-9./]+)?\s*([A-Za-z]+)?\s*(.*)$", text)
    if not match:
        return {"quantity": "", "unit": "", "name": text}
    quantity = (match.group(1) or "").strip()
    unit = (match.group(2) or "").strip()
    name = (match.group(3) or "").strip() or text
    return {"quantity": quantity, "unit": unit, "name": name}


def stringify_ingredient(quantity: str, unit: str, name: str):
    chunks = [quantity.strip(), unit.strip(), name.strip()]
    return " ".join([x for x in chunks if x]).strip()


class RecipeForm(forms.ModelForm):
    tags_text = forms.CharField(required=False, help_text="Comma-separated tags")
    ingredients = forms.CharField(widget=forms.HiddenInput())
    instructions = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = Recipe
        fields = [
            "name",
            "description",
            "ingredients",
            "instructions",
            "cuisine_type",
            "preparation_time",
            "servings",
            "difficulty_level",
            "image",
            "is_favorite",
            "status",
            "is_public",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)
        instance = getattr(self, "instance", None)
        if self.is_bound:
            ingredients_text = (self.data.get("ingredients") or "").strip()
            instructions_text = (self.data.get("instructions") or "").strip()
            self.initial_ingredients = [parse_ingredient_line(x) for x in ingredients_text.splitlines() if x.strip()]
            self.initial_steps = [x.strip() for x in instructions_text.splitlines() if x.strip()]
            if not self.initial_ingredients:
                self.initial_ingredients = [{"quantity": "", "unit": "", "name": ""}]
            if not self.initial_steps:
                self.initial_steps = [""]
            return
        if instance and instance.pk:
            self.fields["tags_text"].initial = ", ".join(instance.tags.values_list("name", flat=True))
            self.initial_ingredients = [parse_ingredient_line(x) for x in instance.ingredients.splitlines() if x.strip()]
            self.initial_steps = [x.strip() for x in instance.instructions.splitlines() if x.strip()]
        else:
            self.initial_ingredients = [{"quantity": "", "unit": "", "name": ""}]
            self.initial_steps = [""]

    def clean(self):
        cleaned = super().clean()
        ingredients = (cleaned.get("ingredients") or "").strip()
        instructions = (cleaned.get("instructions") or "").strip()
        if not ingredients:
            self.add_error("ingredients", "Add at least one ingredient.")
        if not instructions:
            self.add_error("instructions", "Add at least one instruction step.")
        return cleaned

    def save(self, commit=True):
        recipe = super().save(commit=commit)
        tags_text = self.cleaned_data.get("tags_text", "")
        tag_names = [x.strip().lower() for x in tags_text.split(",") if x.strip()]
        tags = []
        for name in sorted(set(tag_names)):
            tag, _ = RecipeTag.objects.get_or_create(name=name)
            tags.append(tag)
        if commit:
            recipe.tags.set(tags)
        else:
            self._pending_tags = tags
        return recipe

    def save_m2m(self):
        super().save_m2m()
        if hasattr(self, "_pending_tags"):
            self.instance.tags.set(self._pending_tags)


class AIRecipeGenerateForm(forms.Form):
    available_ingredients = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Comma-separated or newline-separated ingredients.",
    )
    dietary_restriction = forms.CharField(required=False)
    cuisine_type = forms.CharField(required=False)
    max_prep_time = forms.IntegerField(required=False, min_value=5, max_value=480)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)


class AIMealPlannerForm(forms.Form):
    days = forms.IntegerField(min_value=3, max_value=14, initial=7)
    max_prep_time = forms.IntegerField(required=False, min_value=10, max_value=180)
    dietary_restriction = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)


class ShareRecipeForm(forms.Form):
    target = forms.CharField(help_text="Username or email")
    permission = forms.ChoiceField(choices=RecipeShare.PERMISSION_CHOICES)

    def __init__(self, *args, request_user=None, **kwargs):
        self.request_user = request_user
        super().__init__(*args, **kwargs)
        _apply_styles(self)

    def clean_target(self):
        target = self.cleaned_data["target"].strip()
        if "@" in target:
            user = User.objects.filter(email__iexact=target).first()
        else:
            user = User.objects.filter(username__iexact=target).first()
        if not user:
            raise forms.ValidationError("User not found.")
        if self.request_user and user.pk == self.request_user.pk:
            raise forms.ValidationError("You cannot share with yourself.")
        self.cleaned_data["target_user"] = user
        return target


class RecipeCommentForm(forms.ModelForm):
    class Meta:
        model = RecipeComment
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a comment..."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_styles(self)


class AIPromptOnlyForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea(attrs={"rows": 8}))
