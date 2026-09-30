from django.contrib.auth import views as auth_views
from django.urls import path

from .views import login_view, dashboard, logout_view, team_members, add_sales_employee, sales_employee_detail,edit_sales_employee


urlpatterns = [
    path("", login_view, name="login"),
    path("dashboard/", dashboard, name="dashboard"),
    path("logout/", logout_view, name="logout"),
    path("team-members/", team_members, name="team_members"),
    path("team-members/add/",add_sales_employee,name="add_sales_employee"),
    path(
    "team-members/<int:user_id>/",
    sales_employee_detail,
    name="sales_employee_detail",
),

path(
    "team-members/<int:user_id>/edit/",
    edit_sales_employee,
    name="edit_sales_employee",
),
path(
    "forgot-password/",
    auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        email_template_name="accounts/password_reset_email.html",
        subject_template_name="accounts/password_reset_subject.txt",
    ),
    name="password_reset",
),
    path(
        "forgot-password/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),

    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),

    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]