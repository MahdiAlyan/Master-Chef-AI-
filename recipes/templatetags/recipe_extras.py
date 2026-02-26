import re

from django import template
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter
def split_lines(value):
    if not value:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


@register.filter
def preview_text(value, limit=140):
    text = (value or "").strip()
    try:
        limit = int(limit)
    except Exception:
        limit = 140
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


@register.filter
def highlight(text, query):
    if not text:
        return ""
    escaped = conditional_escape(text)
    q = (query or "").strip()
    if not q:
        return escaped
    pattern = re.compile(re.escape(q), re.IGNORECASE)
    highlighted = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", str(escaped))
    return mark_safe(highlighted)


@register.simple_tag
def status_icon(status):
    if status == "made_before":
        return format_html("check-circle")
    return format_html("clock")


@register.filter
def can_edit(recipe, user):
    if not recipe:
        return False
    try:
        return recipe.can_edit(user)
    except Exception:
        return False


@register.filter
def can_view(recipe, user):
    if not recipe:
        return False
    try:
        return recipe.can_view(user)
    except Exception:
        return False
