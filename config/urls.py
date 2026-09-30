"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import include, path
from leads import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("leads/", include("leads.urls")),
    path(
        "leads/<str:lead_id>/convert/",
        views.convert_lead_to_customer,
        name="convert_lead_to_customer",
    ),
    path(
        "customers/",
        views.customer_list,
        name="customer_list",
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )