"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.static import serve
from leads import views
from django.conf import settings


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


# Serve uploaded media files
urlpatterns += [
    path(
        "media/<path:path>",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]