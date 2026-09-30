from django import template

from leads.utils import format_currency, format_datetime


register = template.Library()


@register.filter
def currency(value):
    return format_currency(value)


@register.filter
def company_datetime(value):
    return format_datetime(value)

@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None

    return dictionary.get(key)