from .models import CompanySettings


def company_settings(request):
    settings_obj = CompanySettings.objects.first()

    return {
        "company_settings": settings_obj
    }