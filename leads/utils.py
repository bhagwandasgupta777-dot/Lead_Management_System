from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import CompanySettings


CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AED": "د.إ",
    "SGD": "S$",
    "AUD": "A$",
    "CAD": "C$",
    "JPY": "¥",
}


def get_company_settings():
    """
    Return the current company settings.
    Create default settings if none exist.
    """
    settings = CompanySettings.objects.first()

    if not settings:
        settings = CompanySettings.objects.create(
            company_name="Company",
            timezone="Asia/Kolkata",
            currency="INR",
        )

    return settings


def get_currency_symbol():
    """
    Return the symbol for the company's configured currency.
    """
    settings = get_company_settings()

    return CURRENCY_SYMBOLS.get(
        settings.currency,
        settings.currency,
    )


def format_currency(amount):
    """
    Format an amount using the company's configured currency.
    """
    if amount is None:
        amount = 0

    symbol = get_currency_symbol()

    return f"{symbol}{amount:,.0f}"


def get_company_timezone():
    """
    Return the company's configured timezone.
    """
    settings = get_company_settings()

    return ZoneInfo(settings.timezone)


def format_datetime(value):
    """
    Convert a Django datetime into the company's configured timezone.
    """
    if not value:
        return ""

    local_time = timezone.localtime(
        value,
        get_company_timezone(),
    )

    return local_time.strftime("%d %b %Y, %I:%M %p")