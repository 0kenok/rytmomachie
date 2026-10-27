from os.path import getmtime

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def asset(path):
    """Static URL with the file's modification time appended, so browsers
    fetch a fresh copy whenever the file changes instead of a cached one."""
    url = static(path)
    found = finders.find(path)
    if not found:
        return url
    return f"{url}?v={int(getmtime(found))}"
