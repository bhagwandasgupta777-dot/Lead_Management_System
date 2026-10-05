from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render,get_object_or_404
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, time, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.cache import never_cache

from leads.models import Lead, LeadTask, LeadActivity, Notification
from .models import User

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect("dashboard")

        messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")


@login_required
def dashboard(request):

    # =========================================================
    # LEAD DATA
    # =========================================================

    if request.user.role in ["ADMIN", "MANAGER"]:
        leads = Lead.objects.all()
    else:
        leads = Lead.objects.filter(
            assigned_to=request.user
        )

    total_leads = leads.count()

    new_leads = leads.filter(
        status=Lead.Status.NEW
    ).count()

    leads_contacted = leads.filter(
        status=Lead.Status.CONTACTED
    ).count()

    leads_qualified = leads.filter(
        status=Lead.Status.QUALIFIED
    ).count()

    leads_proposal = leads.filter(
        status=Lead.Status.PROPOSAL
    ).count()

    leads_negotiation = leads.filter(
        status=Lead.Status.NEGOTIATION
    ).count()

    hot_leads = leads.filter(
        temperature=Lead.Temperature.HOT
    ).exclude(
        status__in=[
            Lead.Status.WON,
            Lead.Status.LOST,
        ]
    ).count()

    won_leads = leads.filter(
        status=Lead.Status.WON
    ).count()

    lost_leads = leads.filter(
        status=Lead.Status.LOST
    ).count()


    # =========================================================
    # PIPELINE VALUE
    # =========================================================

    pipeline_value = leads.filter(
        status__in=[
            Lead.Status.NEW,
            Lead.Status.CONTACTED,
            Lead.Status.QUALIFIED,
            Lead.Status.PROPOSAL,
            Lead.Status.NEGOTIATION,
        ]
    ).aggregate(
        total=Sum("lead_value")
    )["total"] or 0


    # =========================================================
    # WON VALUE
    # =========================================================

    won_value = leads.filter(
        status=Lead.Status.WON
    ).aggregate(
        total=Sum("lead_value")
    )["total"] or 0


    # =========================================================
    # TASK DATA
    # =========================================================

    if request.user.role in ["ADMIN", "MANAGER"]:
        tasks = LeadTask.objects.all()
    else:
        tasks = LeadTask.objects.filter(
            assigned_to=request.user
        )

    pending_tasks = tasks.filter(
        status=LeadTask.Status.PENDING
    ).count()

    overdue_tasks = sum(
        1
        for task in tasks.filter(
            status=LeadTask.Status.PENDING
        )
        if task.is_overdue
    )


    # =========================================================
    # RECENT ACTIVITY
    # =========================================================

    if request.user.role in ["ADMIN", "MANAGER"]:

        recent_activities = (
            LeadActivity.objects
            .select_related(
                "lead",
                "created_by"
            )
            .order_by("-created_at")[:8]
        )

    else:

        recent_activities = (
            LeadActivity.objects
            .select_related(
                "lead",
                "created_by"
            )
            .filter(
                lead__assigned_to=request.user
            )
            .order_by("-created_at")[:8]
        )


    # =========================================================
    # TODAY'S ACTIVITY
    # =========================================================

    today = timezone.localdate()

    start_of_day = timezone.make_aware(
        datetime.combine(
            today,
            time.min
        )
    )

    end_of_day = start_of_day + timedelta(days=1)


    if request.user.role in ["ADMIN", "MANAGER"]:

        today_activities = LeadActivity.objects.filter(
            created_at__gte=start_of_day,
            created_at__lt=end_of_day
        )

        today_tasks = LeadTask.objects.filter(
            status=LeadTask.Status.COMPLETED,
            completed_at__gte=start_of_day,
            completed_at__lt=end_of_day
        )

    else:

        today_activities = LeadActivity.objects.filter(
            lead__assigned_to=request.user,
            created_at__gte=start_of_day,
            created_at__lt=end_of_day
        )

        today_tasks = LeadTask.objects.filter(
            assigned_to=request.user,
            status=LeadTask.Status.COMPLETED,
            completed_at__gte=start_of_day,
            completed_at__lt=end_of_day
        )


    # =========================================================
    # TODAY'S COUNTS
    # =========================================================

    today_calls = today_activities.filter(
        activity_type=LeadActivity.ActivityType.CALL
    ).count()

    today_emails = today_activities.filter(
    activity_type=LeadActivity.ActivityType.EMAIL
    ).count()

    today_messages = today_activities.filter(
        activity_type=LeadActivity.ActivityType.WHATSAPP
    ).count()

    today_meetings = today_activities.filter(
        activity_type=LeadActivity.ActivityType.MEETING
    ).count()

    today_tasks_done = today_tasks.count()


    # =========================================================
    # MY LEADS
    # =========================================================

    my_leads = (
      leads
      .prefetch_related("documents")
      .order_by("-created_at")[:5]
    )


    # =========================================================
# NOTIFICATIONS
# =========================================================


    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    # =========================================================
    # DASHBOARD CONTEXT
    # =========================================================

    context = {

        # Lead statistics
        "total_leads": total_leads,
        "new_leads": new_leads,
        "hot_leads": hot_leads,
        "won_leads": won_leads,
        "lost_leads": lost_leads,

        # Pipeline
        "leads_contacted": leads_contacted,
        "leads_qualified": leads_qualified,
        "leads_proposal": leads_proposal,
        "leads_negotiation": leads_negotiation,
        "pipeline_value": pipeline_value,
        "unread_notifications": unread_notifications,
        "won_value": won_value,

        # Tasks
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,

        # Leads
        "my_leads": my_leads,

        # Recent activity
        "recent_activities": recent_activities,

        # Today's activity
        "today_calls": today_calls,
        "today_emails": today_emails,
        "today_messages": today_messages,
        "today_meetings": today_meetings,
        "today_tasks_done": today_tasks_done,
    }


    return render(
        request,
        "dashboard.html",
        context
    )


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def team_members(request):
    # Only Admin can manage users
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "You are not allowed to manage users.")
        return redirect("dashboard")

    sales_employees = User.objects.filter(
        role=User.Role.SALES
    ).order_by("first_name", "username")

    managers = User.objects.filter(
        role=User.Role.MANAGER
    ).order_by("first_name", "username")

    context = {
        "sales_employees": sales_employees,
        "managers": managers,
    }

    return render(
        request,
        "accounts/team_members.html",
        context
    )
@login_required
def add_sales_employee(request):

    # Only Admin can create Sales Employees
    if request.user.role != User.Role.ADMIN:
        messages.error(
            request,
            "You are not allowed to create Sales Employees."
        )
        return redirect("dashboard")

    if request.method == "POST":

        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        errors = []

        # -----------------------------------------
        # FIRST NAME
        # -----------------------------------------

        if not first_name:

            errors.append(
                "First name is required."
            )

        elif len(first_name) < 2:

            errors.append(
                "First name must contain at least 2 characters."
            )

        elif not first_name.replace(" ", "").isalpha():

            errors.append(
                "First name can contain letters and spaces only."
            )

        # -----------------------------------------
        # LAST NAME
        # -----------------------------------------

        if last_name:

            if not last_name.replace(" ", "").isalpha():

                errors.append(
                    "Last name can contain letters and spaces only."
                )

        # -----------------------------------------
        # EMAIL
        # -----------------------------------------

        if not email:

            errors.append(
                "Email address is required."
            )

        else:

            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError

            try:

                validate_email(email)

            except ValidationError:

                errors.append(
                    "Enter a valid email address."
                )

        # -----------------------------------------
        # USERNAME
        # -----------------------------------------

        if not username:

            errors.append(
                "Username is required."
            )

        else:

            if len(username) < 4:

                errors.append(
                    "Username must contain at least 4 characters."
                )

            if len(username) > 30:

                errors.append(
                    "Username cannot contain more than 30 characters."
                )

            if " " in username:

                errors.append(
                    "Username cannot contain spaces."
                )

            if not username.replace("_", "").replace("-", "").isalnum():

                errors.append(
                    "Username can contain only letters, numbers, "
                    "underscores and hyphens."
                )

            if User.objects.filter(
                username__iexact=username
            ).exists():

                errors.append(
                    "This username is already in use."
                )

        # -----------------------------------------
        # EMAIL UNIQUE
        # -----------------------------------------

        if email and User.objects.filter(
            email__iexact=email
        ).exists():

            errors.append(
                "This email address is already registered."
            )

        # -----------------------------------------
        # PASSWORD
        # -----------------------------------------

        if not password:

            errors.append(
                "Password is required."
            )

        else:

            if len(password) < 8:

                errors.append(
                    "Password must contain at least 8 characters."
                )

            if len(password) > 128:

                errors.append(
                    "Password cannot contain more than 128 characters."
                )

            if password.isdigit():

                errors.append(
                    "Password must contain at least one letter."
                )

            if password.isalpha():

                errors.append(
                    "Password should contain numbers or special characters."
                )

        # -----------------------------------------
        # CONFIRM PASSWORD
        # -----------------------------------------

        if not confirm_password:

            errors.append(
                "Please confirm the password."
            )

        elif password != confirm_password:

            errors.append(
                "Passwords do not match."
            )

        # -----------------------------------------
        # SHOW ERRORS
        # -----------------------------------------

        if errors:

            for error in errors:

                messages.error(
                    request,
                    error
                )

            return render(
                request,
                "accounts/add_sales_employee.html"
            )

        # -----------------------------------------
        # CREATE USER
        # -----------------------------------------

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.Role.SALES,
        )

        user.is_active = True
        user.save()

        # -----------------------------------------
        # SEND LOGIN CREDENTIALS EMAIL
        # -----------------------------------------

        login_url = request.build_absolute_uri("/")

        subject = (
            "Your Lead Management System Login Credentials"
        )

        message = f"""
Hello {first_name},

Your Sales Employee account has been created for the Lead Management System.

Your login credentials are:

Username: {username}
Email: {email}
Password: {password}

Login here:
{login_url}

Please log in using these credentials and change your password after your first login.

Regards,
Admin
Lead Management System
"""

        try:

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            messages.success(
                request,
                f"Sales Employee {first_name} {last_name} "
                f"created successfully. "
                f"Login credentials have been sent to {email}."
            )

        except Exception as e:

            messages.warning(
                request,
                f"Sales Employee {first_name} {last_name} "
                f"was created, but the credentials email "
                f"could not be sent."
            )

        return redirect("team_members")

    return render(
        request,
        "accounts/add_sales_employee.html"
    )
@login_required
def sales_employee_detail(request, user_id):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "You are not allowed to view employee details.")
        return redirect("dashboard")

    employee = get_object_or_404(
        User,
        id=user_id,
        role=User.Role.SALES
    )

    assigned_leads = Lead.objects.filter(
        assigned_to=employee
    ).select_related("assigned_to").order_by("-created_at")

    # Filter
    lead_filter = request.GET.get("lead_filter", "all")

    if lead_filter == "active":
        assigned_leads = assigned_leads.exclude(
            status__in=[Lead.Status.WON, Lead.Status.LOST]
        )

    elif lead_filter == "won":
        assigned_leads = assigned_leads.filter(
            status=Lead.Status.WON
        )

    elif lead_filter == "lost":
        assigned_leads = assigned_leads.filter(
            status=Lead.Status.LOST
        )

    assigned_tasks = LeadTask.objects.filter(
        assigned_to=employee
    ).select_related("lead").order_by("due_date")

    context = {
        "employee": employee,
        "assigned_leads": assigned_leads,
        "assigned_tasks": assigned_tasks,

        # Counts should always remain total counts
        "total_leads": Lead.objects.filter(
            assigned_to=employee
        ).count(),

        "active_leads": Lead.objects.filter(
            assigned_to=employee
        ).exclude(
            status__in=[Lead.Status.WON, Lead.Status.LOST]
        ).count(),

        "won_leads": Lead.objects.filter(
            assigned_to=employee,
            status=Lead.Status.WON
        ).count(),

        "lost_leads": Lead.objects.filter(
            assigned_to=employee,
            status=Lead.Status.LOST
        ).count(),

        "total_tasks": assigned_tasks.count(),

        "lead_filter": lead_filter,
    }

    return render(
        request,
        "accounts/sales_employee_detail.html",
        context
    )


@login_required
def edit_sales_employee(request, user_id):

    # Only Admin can edit Sales Employees
    if request.user.role != User.Role.ADMIN:
        messages.error(
            request,
            "You are not allowed to edit employees."
        )
        return redirect("dashboard")

    employee = get_object_or_404(
        User,
        id=user_id,
        role=User.Role.SALES
    )

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        first_name = request.POST.get(
            "first_name",
            ""
        ).strip()

        last_name = request.POST.get(
            "last_name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip().lower()

        password = request.POST.get(
            "password",
            ""
        )

        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )

        is_active = request.POST.get("is_active") == "on"

        errors = []

        # -----------------------------
        # USERNAME
        # -----------------------------

        if not username:

            errors.append(
                "Username is required."
            )

        elif len(username) < 3:

            errors.append(
                "Username must contain at least 3 characters."
            )

        elif User.objects.filter(
            username__iexact=username
        ).exclude(
            id=employee.id
        ).exists():

            errors.append(
                "This username is already taken."
            )

        # -----------------------------
        # FIRST NAME
        # -----------------------------

        if not first_name:

            errors.append(
                "First name is required."
            )

        elif len(first_name) < 2:

            errors.append(
                "First name must contain at least 2 characters."
            )

        elif not first_name.replace(" ", "").isalpha():

            errors.append(
                "First name can contain letters and spaces only."
            )

        # -----------------------------
        # LAST NAME
        # -----------------------------

        if last_name:

            if not last_name.replace(
                " ",
                ""
            ).isalpha():

                errors.append(
                    "Last name can contain letters and spaces only."
                )

        # -----------------------------
        # EMAIL
        # -----------------------------

        if not email:

            errors.append(
                "Email address is required."
            )

        else:

            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError

            try:

                validate_email(email)

            except ValidationError:

                errors.append(
                    "Enter a valid email address."
                )

        # -----------------------------
        # EMAIL UNIQUE
        # -----------------------------

        if email:

            email_exists = User.objects.filter(
                email__iexact=email
            ).exclude(
                id=employee.id
            ).exists()

            if email_exists:

                errors.append(
                    "This email address is already registered."
                )

        # -----------------------------
        # PASSWORD
        # -----------------------------

        if password:

            if len(password) < 8:

                errors.append(
                    "Password must contain at least 8 characters."
                )

            elif password.isdigit():

                errors.append(
                    "Password must contain at least one letter."
                )

            elif password.isalpha():

                errors.append(
                    "Password should contain numbers or special characters."
                )

            elif password != confirm_password:

                errors.append(
                    "Passwords do not match."
                )

        # -----------------------------
        # SHOW ERRORS
        # -----------------------------

        if errors:

            for error in errors:

                messages.error(
                    request,
                    error
                )

            return render(
                request,
                "accounts/edit_sales_employee.html",
                {
                    "employee": employee,
                }
            )

        # -----------------------------
        # SAVE EMPLOYEE
        # -----------------------------

        employee.username = username
        employee.first_name = first_name
        employee.last_name = last_name
        employee.email = email
        employee.is_active = is_active

        # Only change password if Admin entered one
        if password:

            employee.set_password(
                password
            )

        employee.save()

        # -----------------------------
        # SUCCESS MESSAGE
        # -----------------------------

        messages.success(
            request,
            f"{employee.first_name} "
            f"{employee.last_name} "
            f"updated successfully."
        )

        return redirect(
            "sales_employee_detail",
            user_id=employee.id
        )

    return render(
        request,
        "accounts/edit_sales_employee.html",
        {
            "employee": employee,
        }
    )