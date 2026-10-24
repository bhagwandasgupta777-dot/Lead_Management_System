from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Lead, LeadActivity, LeadTask, LeadAssignmentHistory,Customer,Deal,LeadDocument,Notification, TaskAssignmentHistory,CompanySettings, SupportTicket
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
import re
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.core.validators import validate_email
from PIL import Image
from accounts.models import User
from .models import CompanySettings,CURRENCY_CHOICES,TIMEZONE_CHOICES
from django.http import JsonResponse
# ============================================================
# LEAD STAGE WORKFLOW
# ============================================================

STAGE_ORDER = [
    "NEW",
    "CONTACTED",
    "QUALIFIED",
    "PROPOSAL",
    "NEGOTIATION",
    "WON",
]


STAGE_CONFIG = {
    "NEW": {
        "number": 1,
        "title": "New Lead",
        "description": "Review the new lead and start the sales process.",
        "next": "CONTACTED",
        "next_label": "Contacted",
        "section_title": "Lead Information",
    },

    "CONTACTED": {
        "number": 2,
        "title": "Contacted",
        "description": "Call the customer and understand their requirement.",
        "next": "QUALIFIED",
        "next_label": "Qualified",
        "section_title": "Contact Details",
    },

    "QUALIFIED": {
        "number": 3,
        "title": "Qualified",
        "description": "Confirm the customer's requirement, budget and timeline.",
        "next": "PROPOSAL",
        "next_label": "Proposal",
        "section_title": "Qualification Details",
    },

    "PROPOSAL": {
        "number": 4,
        "title": "Proposal",
        "description": "Prepare and send the proposal to the customer.",
        "next": "NEGOTIATION",
        "next_label": "Negotiation",
        "section_title": "Proposal Details",
    },

    "NEGOTIATION": {
        "number": 5,
        "title": "Negotiation",
        "description": "Discuss pricing and terms with the customer.",
        "next": "WON",
        "next_label": "Won",
        "section_title": "Negotiation Details",
    },

    "WON": {
        "number": 6,
        "title": "Won",
        "description": "Complete the customer and deal conversion.",
        "next": None,
        "next_label": None,
        "section_title": "Final Details",
    },
}
# ============================================================
# LEAD STAGE GUIDANCE
# ============================================================

STAGE_GUIDANCE = {
    "NEW": {
        "title": "New Lead",
        "next_stage": "CONTACTED",
        "next_stage_label": "Contacted",
        "next_action": "Contact the customer and understand their requirement.",
        "steps": [
            "Make first contact",
            "Understand customer requirement",
            "Record the conversation",
            "Schedule the next follow-up",
        ],
    },

    "CONTACTED": {
        "title": "Contacted",
        "next_stage": "QUALIFIED",
        "next_stage_label": "Qualified",
        "next_action": "Understand the customer's requirement and confirm their interest.",
        "steps": [
            "Confirm customer requirements",
            "Identify budget",
            "Identify expected timeline",
            "Schedule the next follow-up",
        ],
    },

    "QUALIFIED": {
        "title": "Qualified",
        "next_stage": "PROPOSAL",
        "next_stage_label": "Proposal",
        "next_action": "Confirm that the lead is a genuine sales opportunity.",
        "steps": [
            "Confirm requirements",
            "Confirm budget",
            "Identify decision maker",
            "Confirm purchase timeline",
        ],
    },

    "PROPOSAL": {
        "title": "Proposal",
        "next_stage": "NEGOTIATION",
        "next_stage_label": "Negotiation",
        "next_action": "Prepare and send the proposal to the customer.",
        "steps": [
            "Prepare proposal",
            "Send proposal",
            "Confirm proposal value",
            "Schedule the next follow-up",
        ],
    },

    "NEGOTIATION": {
        "title": "Negotiation",
        "next_stage": "WON",
        "next_stage_label": "Won",
        "next_action": "Discuss pricing and terms and work towards closing the deal.",
        "steps": [
            "Follow up with customer",
            "Handle customer objections",
            "Finalize pricing and terms",
            "Confirm expected closing date",
        ],
    },

    "WON": {
        "title": "Won",
        "next_stage": None,
        "next_stage_label": None,
        "next_action": "Complete customer and deal conversion.",
        "steps": [
            "Create or confirm customer",
            "Create or confirm deal",
            "Complete required customer information",
        ],
    },

    "LOST": {
        "title": "Lost",
        "next_stage": None,
        "next_stage_label": None,
        "next_action": "Record why the opportunity was lost.",
        "steps": [
            "Select lost reason",
            "Record useful notes",
            "Keep the lead available for reporting",
        ],
    },
}


@login_required
def lead_list(request):
    # Admin and Manager can see all leads.
    # Sales Employee can see only their assigned leads.
    if request.user.role in ["ADMIN", "MANAGER"]:
        leads = Lead.objects.select_related("assigned_to").all()
    else:
        leads = Lead.objects.select_related("assigned_to").filter(
            assigned_to=request.user
        )

    User = get_user_model()

    sales_users = User.objects.filter(
        role=User.Role.SALES,
        is_active=True
    ).order_by("username")

    # ---------------------------------------------------------
    # SEARCH
    # ---------------------------------------------------------

    search = request.GET.get("search", "").strip()

    if search:
        from django.db.models import Q

        leads = leads.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(company__icontains=search)
            | Q(location__icontains=search)
            | Q(category__icontains=search)
            | Q(lead_id__icontains=search)
        )

    # ---------------------------------------------------------
    # STATUS FILTER
    # ---------------------------------------------------------

    status_filter = request.GET.get(
        "status",
        ""
    ).strip()

    if status_filter:
        leads = leads.filter(
            status=status_filter
        )

    # ---------------------------------------------------------
    # TEMPERATURE FILTER
    # ---------------------------------------------------------

    temperature_filter = request.GET.get(
        "temperature",
        ""
    ).strip()

    if temperature_filter:
        leads = leads.filter(
            temperature=temperature_filter
        )

        # Dashboard Hot Leads means active opportunities.
        # Won and Lost leads should not appear when
        # filtering Hot Leads from the dashboard.
        if temperature_filter == Lead.Temperature.HOT:
            leads = leads.exclude(
                status__in=[
                    Lead.Status.WON,
                    Lead.Status.LOST,
                ]
            )

    # ---------------------------------------------------------
    # PRIORITY FILTER
    # ---------------------------------------------------------

    priority_filter = request.GET.get(
        "priority",
        ""
    ).strip()

    if priority_filter:
        leads = leads.filter(
            priority=priority_filter
        )

    # ---------------------------------------------------------
    # ASSIGNED EMPLOYEE FILTER
    # ---------------------------------------------------------

    assigned_to_filter = request.GET.get(
        "assigned_to",
        ""
    ).strip()

    if assigned_to_filter:
        leads = leads.filter(
            assigned_to_id=assigned_to_filter
        )

    # ---------------------------------------------------------
    # SOURCE FILTER
    # ---------------------------------------------------------

    source_filter = request.GET.get(
        "source",
        ""
    ).strip()

    if source_filter:
        leads = leads.filter(
            source=source_filter
        )

    # ---------------------------------------------------------
    # SORTING
    # ---------------------------------------------------------

    sort = request.GET.get(
        "sort",
        ""
    ).strip()

    if sort == "score_high":
        leads = leads.order_by(
            "-lead_score",
            "-created_at"
        )

    elif sort == "score_low":
        leads = leads.order_by(
            "lead_score",
            "-created_at"
        )

    else:
        leads = leads.order_by(
            "-created_at",
            "-id"
        )

    # ---------------------------------------------------------
    # PAGINATION
    # ---------------------------------------------------------

    paginator = Paginator(
        leads,
        10
    )

    page_number = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        page_number
    )

    # ---------------------------------------------------------
    # STAGE GUIDANCE
    # ---------------------------------------------------------
    # Attach the appropriate workflow guidance to each lead.
    #
    # Example:
    # NEW -> Contact the customer
    # CONTACTED -> Qualify the lead
    # QUALIFIED -> Prepare proposal
    # PROPOSAL -> Start negotiation
    # NEGOTIATION -> Close the deal
    # ---------------------------------------------------------

    for lead in page_obj:
        lead.stage_guidance = STAGE_GUIDANCE.get(
            lead.status,
            {}
        )

    # ---------------------------------------------------------
    # RENDER
    # ---------------------------------------------------------

    return render(
        request,
        "leads/lead_list.html",
        {
            "leads": page_obj,
            "page_obj": page_obj,

            # Search
            "search": search,

            # Filters
            "status_filter": status_filter,
            "temperature_filter": temperature_filter,
            "priority_filter": priority_filter,
            "assigned_to_filter": assigned_to_filter,
            "source_filter": source_filter,

            # Users
            "sales_users": sales_users,

            # Choices
            "status_choices": Lead.Status.choices,
            "temperature_choices": Lead.Temperature.choices,
            "priority_choices": Lead.Priority.choices,
            "source_choices": Lead.Source.choices,
        },
    )


@login_required
def move_to_next_stage(request, lead_id):
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("lead_list")

    lead = get_object_or_404(Lead, lead_id=lead_id)

    # Sales employees can only update their own assigned leads
    if request.user.role == "SALES" and lead.assigned_to != request.user:
        messages.error(request, "You are not allowed to update this lead.")
        return redirect("lead_list")

    # Define the normal stage sequence
    next_stages = {
        Lead.Status.NEW: Lead.Status.CONTACTED,
        Lead.Status.CONTACTED: Lead.Status.QUALIFIED,
        Lead.Status.QUALIFIED: Lead.Status.PROPOSAL,
        Lead.Status.PROPOSAL: Lead.Status.NEGOTIATION,
        Lead.Status.NEGOTIATION: Lead.Status.WON,
    }

    current_stage = lead.status
    next_stage = next_stages.get(current_stage)

    # No next stage for Won or Lost
    if not next_stage:
        messages.warning(
            request,
            "This lead cannot be moved to another stage."
        )
        return redirect("lead_list")

    old_stage = lead.get_status_display()

    # Move to next stage
    lead.status = next_stage
    lead.save()

    new_stage = lead.get_status_display()

    # Record the stage change in timeline
    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
        description=f"Lead stage changed from {old_stage} to {new_stage}.",
        created_by=request.user,
    )

    # If lead becomes Won, create Customer and Deal
    if next_stage == Lead.Status.WON:

        customer = getattr(lead, "customer", None)

        if not customer:
            customer = Customer.objects.create(
                first_name=lead.first_name,
                last_name=lead.last_name,
                phone=lead.phone,
                whatsapp_number=lead.whatsapp_number,
                email=lead.email,
                company=lead.company,
                source=lead.get_source_display(),
                assigned_to=lead.assigned_to,
                lead=lead,
            )

        # Create a deal only if one does not already exist
        if not lead.customer.deals.exists():
            Deal.objects.create(
                customer=customer,
                title=f"Deal for {customer.first_name} {customer.last_name}".strip(),
                deal_value=lead.lead_value,
                status=Deal.Status.WON,
                assigned_to=lead.assigned_to,
                notes=f"Deal created automatically from {lead.lead_id}.",
            )

        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.ActivityType.NOTE,
            description="Lead converted to customer and deal after reaching Won stage.",
            created_by=request.user,
        )

    messages.success(
        request,
        f"{lead.lead_id} moved from {old_stage} to {new_stage}."
    )

    return redirect("lead_list")

from django.shortcuts import get_object_or_404



@login_required
def lead_detail(request, lead_id):
    # Admin and Manager can view all leads.
    # Sales Employees can view only their assigned leads.
    if request.user.role in ["ADMIN", "MANAGER"]:
        lead_queryset = Lead.objects.all()
    else:
        lead_queryset = Lead.objects.filter(
            assigned_to=request.user
        )

    lead = get_object_or_404(
        lead_queryset.select_related("assigned_to"),
        lead_id=lead_id
    )

    activities = lead.activities.select_related("created_by").all()
    tasks = lead.tasks.select_related("assigned_to").all()

    assignment_history = lead.assignment_history.select_related(
        "assigned_to",
        "assigned_by"
    ).all()

    # Get active Sales Employees for assignment dropdown.
    User = get_user_model()
    sales_users = User.objects.filter(
        role=User.Role.SALES,
        is_active=True
    ).order_by("username")

    stage_data = lead.stage_data or {}
    selected_stage = request.GET.get("stage", "").upper()

    return render(
        request,
        "leads/lead_detail.html",
        {
            "lead": lead,
            "activities": activities,
            "tasks": tasks,
            "assignment_history": assignment_history,
            "sales_users": sales_users,
            "stage_data": stage_data,
            "selected_stage": selected_stage,
        },
    )

@login_required
def save_call_outcome(request, lead_id):
    from django.contrib import messages
    from django.http import HttpResponseNotAllowed
    from django.utils import timezone
    from django.shortcuts import redirect
    from .models import Lead, LeadActivity

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    # Admin and Manager can access all leads.
    # Sales Employees can access only their assigned leads.
    if request.user.role in ["ADMIN", "MANAGER"]:
        lead_queryset = Lead.objects.all()
    else:
        lead_queryset = Lead.objects.filter(
            assigned_to=request.user
        )

    lead = get_object_or_404(lead_queryset, lead_id=lead_id)

    outcome = request.POST.get("call_outcome", "").strip()
    notes = request.POST.get("description", "").strip()

    allowed_outcomes = {
        choice[0] for choice in LeadActivity.CallOutcome.choices
    }

    if outcome not in allowed_outcomes:
        messages.error(request, "Please select a valid call outcome.")
        return redirect("lead_detail", lead_id=lead.lead_id)

    # Save the call outcome in the lead's activity history.
    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.CALL,
        call_outcome=outcome,
        description=notes or f"Call outcome: {outcome}",
        created_by=request.user,
    )

    messages.success(request, "Call outcome saved successfully.")
    return redirect("lead_detail", lead_id=lead.lead_id)


@login_required
def assign_lead(request, lead_id):

    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(
            request,
            "You do not have permission to assign leads."
        )
        return redirect(
            "lead_detail",
            lead_id=lead_id
        )

    lead = get_object_or_404(
        Lead,
        lead_id=lead_id
    )

    if request.method == "POST":

        User = get_user_model()

        assigned_user_id = request.POST.get(
            "assigned_to"
        )

        assigned_user = User.objects.filter(
            id=assigned_user_id,
            role=User.Role.SALES,
            is_active=True
        ).first()

        if not assigned_user:
            messages.error(
                request,
                "Please select a valid Sales Employee."
            )

            return redirect(
                "lead_detail",
                lead_id=lead.lead_id
            )

        old_assigned_to = lead.assigned_to

        # Update assignment
        lead.assigned_to = assigned_user
        lead.save()

        # =========================================================
        # ASSIGNMENT CHANGED
        # =========================================================

        if old_assigned_to != assigned_user:

            # Record assignment history
            LeadAssignmentHistory.objects.create(
                lead=lead,
                assigned_to=assigned_user,
                assigned_by=request.user,
            )

            # Record activity in timeline
            LeadActivity.objects.create(
                lead=lead,
                activity_type=LeadActivity.ActivityType.NOTE,
                description=f"Lead assigned to {assigned_user.username}",
                created_by=request.user,
            )

            # =====================================================
            # NOTIFY NEW SALES EMPLOYEE
            # =====================================================

            Notification.objects.create(
                user=assigned_user,
                lead=lead,
                notification_type=Notification.NotificationType.LEAD_ASSIGNED,
                title="New Lead Assigned",
                message=f"Lead {lead.lead_id} has been assigned to you.",
            )

        messages.success(
            request,
            f"{lead.lead_id} assigned to {assigned_user.username} successfully."
        )

        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    return redirect(
        "lead_detail",
        lead_id=lead.lead_id
    )

@login_required
def create_lead(request):
    if request.user.role != "ADMIN":
        messages.error(
            request,
            "Only Admin can create new leads."
        )
        return redirect("lead_list")

    User = get_user_model()

    # Active Sales Employees for assignment
    sales_users = User.objects.filter(
        role=User.Role.SALES,
        is_active=True
    ).order_by("username")

    if request.method == "POST":

        
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()
        whatsapp_number = request.POST.get(
            "whatsapp_number", ""
        ).strip()

        company = request.POST.get("company", "").strip()
        total_employees_raw = request.POST.get(
            "total_employees", ""
        ).strip()

        # Validate mandatory fields
        from django.core.validators import validate_email

        validation_errors = []

        if not email:
            validation_errors.append("Email is required.")
        else:
            try:
                validate_email(email)
            except ValidationError:
                validation_errors.append("Enter a valid email address.")

        if not company:
            validation_errors.append("Company name is required.")

        try:
            total_employees = int(total_employees_raw)
            if total_employees < 1:
                validation_errors.append(
                    "Total employees must be at least 1."
                )
        except (ValueError, TypeError):
            validation_errors.append(
                "Enter a valid total employee count."
            )

        if validation_errors:
            for error in validation_errors:
                messages.error(request, error)

            return render(
                request,
                "leads/lead_form.html",
                {
                    "form_data": request.POST,
                    "source_choices": Lead.Source.choices,
                    "temperature_choices": Lead.Temperature.choices,
                    "priority_choices": Lead.Priority.choices,
                    "sales_users": sales_users,
                }
            )

        whatsapp_number = request.POST.get(
           "whatsapp_number", ""
        ).strip()

        # Validate Indian mobile numbers
        phone_validator = RegexValidator(
            regex=r"^[6-9]\d{9}$",
            message="Enter a valid 10-digit Indian mobile number."
        )

        try:
            phone_validator(phone)

            if whatsapp_number:
                phone_validator(whatsapp_number)

        except ValidationError as error:
            messages.error(request, error.messages[0])

            return render(
                request,
                "leads/lead_form.html",
                {
                    "form_data": request.POST,
                    "source_choices": Lead.Source.choices,
                    "temperature_choices": Lead.Temperature.choices,
                    "priority_choices": Lead.Priority.choices,
                    "sales_users": sales_users,
                }
            )
        


        # =========================================================
        # DUPLICATE PHONE CHECK
        # =========================================================

        if phone and Lead.objects.filter(phone=phone).exists():
            messages.error(
                request,
                "A lead with this phone number already exists."
            )

            return render(
                request,
                "leads/lead_form.html",
                {
                    "form_data": request.POST,
                    "source_choices": Lead.Source.choices,
                    "temperature_choices": Lead.Temperature.choices,
                    "priority_choices": Lead.Priority.choices,
                    "sales_users": sales_users,
                }
            )

        # =========================================================
        # DUPLICATE EMAIL CHECK
        # =========================================================

        if email and Lead.objects.filter(email=email).exists():
            messages.error(
                request,
                "A lead with this email already exists."
            )

            return render(
                request,
                "leads/lead_form.html",
                {
                    "form_data": request.POST,
                    "source_choices": Lead.Source.choices,
                    "temperature_choices": Lead.Temperature.choices,
                    "priority_choices": Lead.Priority.choices,
                    "sales_users": sales_users,
                }
            )

        # =========================================================
        # DECIDE WHO THE LEAD IS ASSIGNED TO
        # =========================================================

        assigned_to = request.user

        # Admin and Manager can choose a Sales Employee
        if request.user.role in ["ADMIN", "MANAGER"]:

            assigned_user_id = request.POST.get("assigned_to")

            if assigned_user_id:

                assigned_user = User.objects.filter(
                    id=assigned_user_id,
                    role=User.Role.SALES,
                    is_active=True
                ).first()

                if assigned_user:
                    assigned_to = assigned_user

        # =========================================================
        # CREATE LEAD
        # =========================================================

        lead = Lead.objects.create(
            first_name=request.POST.get(
                "first_name",
                ""
            ).strip(),

            last_name=request.POST.get(
                "last_name",
                ""
            ).strip(),

            phone=phone,

            whatsapp_number=request.POST.get(
                "whatsapp_number",
                ""
            ).strip(),

            email=email,

            company=company,

            location=request.POST.get(
                "location",
                ""
            ).strip(),
            category=request.POST.get(
                "category",
                ""
            ).strip(),

            total_employees=total_employees,

            source=request.POST.get(
                "source",
                Lead.Source.OTHER
            ),

            temperature=request.POST.get(
                "temperature",
                Lead.Temperature.WARM
            ),

            priority=request.POST.get(
                "priority",
                Lead.Priority.MEDIUM
            ),

            lead_value=request.POST.get(
                "lead_value",
                0
            ) or 0,

            next_follow_up=request.POST.get(
                "next_follow_up"
            ) or None,

            notes=request.POST.get(
                "notes",
                ""
            ).strip(),

            assigned_to=assigned_to,
        )

        # =========================================================
        # RECORD INITIAL ASSIGNMENT
        # =========================================================

        if assigned_to:

            LeadAssignmentHistory.objects.create(
                lead=lead,
                assigned_to=assigned_to,
                assigned_by=request.user,
            )

        # =========================================================
        # NOTIFY SALES EMPLOYEE
        # =========================================================

        # Do not notify the user if they assigned the lead to themselves
        if assigned_to and assigned_to != request.user:

            Notification.objects.create(
                user=assigned_to,
                lead=lead,
                notification_type=Notification.NotificationType.LEAD_ASSIGNED,
                title="New Lead Assigned",
                message=f"Lead {lead.lead_id} has been assigned to you.",
            )

        # =========================================================
        # SUCCESS MESSAGE
        # =========================================================

        messages.success(
            request,
            f"{lead.lead_id} created successfully."
        )

        return redirect(
            "lead_stage_workflow",
            lead_id=lead.lead_id
        )

    # =============================================================
    # SHOW CREATE LEAD FORM
    # =============================================================

    return render(
        request,
        "leads/lead_form.html",
        {
            "source_choices": Lead.Source.choices,
            "temperature_choices": Lead.Temperature.choices,
            "priority_choices": Lead.Priority.choices,
            "sales_users": sales_users,
        }
    )
@login_required
def edit_lead(request, lead_id):
    if request.user.role != "ADMIN":
        messages.error(
            request,
            "Only Admin can edit lead details."
        )
        return redirect("lead_detail", lead_id=lead_id)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    if request.method == "POST":

        # Store values that must be monitored before updating.
        old_assigned_to = lead.assigned_to

        # ---------------------------------------------------------
        # CONTACT INFORMATION
        # ---------------------------------------------------------

        lead.first_name = request.POST.get(
            "first_name",
            ""
        ).strip()

        lead.last_name = request.POST.get(
            "last_name",
            ""
        ).strip()

        lead.phone = request.POST.get(
            "phone",
            ""
        ).strip()

        
        lead.whatsapp_number = request.POST.get(
            "whatsapp_number",
            ""
        ).strip()

        # Validate Indian mobile numbers
        phone_validator = RegexValidator(
            regex=r"^[6-9]\d{9}$",
            message="Enter a valid 10-digit Indian mobile number."
        )

        try:
            phone_validator(lead.phone)

            if lead.whatsapp_number:
                phone_validator(lead.whatsapp_number)

        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("edit_lead", lead_id=lead_id)
       
        # Only validate Email, Company and Total Employees
        from django.core.validators import validate_email

        email = request.POST.get("email", "").strip()
        company = request.POST.get("company", "").strip()
        total_employees_raw = request.POST.get(
            "total_employees", ""
        ).strip()

        if not email:
            messages.error(request, "Email is required.")
            return redirect("edit_lead", lead_id=lead_id)

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Enter a valid email address.")
            return redirect("edit_lead", lead_id=lead_id)

        if not company:
            messages.error(request, "Company name is required.")
            return redirect("edit_lead", lead_id=lead_id)

        try:
            total_employees = int(total_employees_raw)
            if total_employees < 1:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(
                request,
                "Total employees must be at least 1."
            )
            return redirect("edit_lead", lead_id=lead_id)

        lead.email = email
        lead.company = company

        lead.location = request.POST.get(
            "location",
            ""
        ).strip()

        lead.category = request.POST.get(
            "category",
            ""
        ).strip()

        lead.total_employees = total_employees


        # ---------------------------------------------------------
        # LEAD SOURCE
        # ---------------------------------------------------------

        lead.source = request.POST.get(
            "source",
            Lead.Source.OTHER
        )

        # ---------------------------------------------------------
        # IMPORTANT:
        # STATUS IS NOT UPDATED HERE.
        #
        # Stage changes are handled only through the
        # Lead Stage Workflow from the Lead List.
        # ---------------------------------------------------------

        # Keep the existing status unchanged.

        # ---------------------------------------------------------
        # LOST REASON
        # ---------------------------------------------------------

        lead.lost_reason = request.POST.get(
            "lost_reason",
            ""
        ).strip()

        # ---------------------------------------------------------
        # TEMPERATURE
        # ---------------------------------------------------------

        lead.temperature = request.POST.get(
            "temperature",
            Lead.Temperature.WARM
        )

        # ---------------------------------------------------------
        # PRIORITY
        # ---------------------------------------------------------

        lead.priority = request.POST.get(
            "priority",
            Lead.Priority.MEDIUM
        )

        # ---------------------------------------------------------
        # ASSIGN LEAD
        # Only Admin and Manager can assign leads.
        # ---------------------------------------------------------

        User = get_user_model()

        if request.user.role in ["ADMIN", "MANAGER"]:

            assigned_user_id = request.POST.get(
                "assigned_to"
            )

            if assigned_user_id:

                assigned_user = User.objects.filter(
                    id=assigned_user_id,
                    role=User.Role.SALES,
                    is_active=True
                ).first()

                if assigned_user:
                    lead.assigned_to = assigned_user

            else:
                lead.assigned_to = None

        # ---------------------------------------------------------
        # LEAD VALUE
        # ---------------------------------------------------------

        lead.lead_value = request.POST.get(
            "lead_value",
            0
        ) or 0

        # ---------------------------------------------------------
        # NEXT FOLLOW-UP
        # ---------------------------------------------------------

        lead.next_follow_up = (
            request.POST.get("next_follow_up")
            or None
        )

        # ---------------------------------------------------------
        # NOTES
        # ---------------------------------------------------------

        lead.notes = request.POST.get(
            "notes",
            ""
        ).strip()

        # ---------------------------------------------------------
        # SAVE LEAD
        # ---------------------------------------------------------

        lead.save()

        # ---------------------------------------------------------
        # ASSIGNMENT HISTORY
        # ---------------------------------------------------------

        if old_assigned_to != lead.assigned_to:

            LeadAssignmentHistory.objects.create(
                lead=lead,
                assigned_to=lead.assigned_to,
                assigned_by=request.user,
            )

            LeadActivity.objects.create(
                lead=lead,
                activity_type=(
                    LeadActivity.ActivityType.NOTE
                ),
                description=(
                    "Lead assignment updated."
                ),
                created_by=request.user,
            )

        # ---------------------------------------------------------
        # SUCCESS MESSAGE
        # ---------------------------------------------------------

        messages.success(
            request,
            f"{lead.lead_id} updated successfully."
        )

        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    # -------------------------------------------------------------
    # GET REQUEST
    # -------------------------------------------------------------

    User = get_user_model()

    sales_users = User.objects.filter(
        role=User.Role.SALES,
        is_active=True
    ).order_by("username")

    return render(
        request,
        "leads/lead_edit.html",
        {
            "lead": lead,
            "sales_users": sales_users,
            "source_choices": Lead.Source.choices,
            "temperature_choices": Lead.Temperature.choices,
            "priority_choices": Lead.Priority.choices,
        },
    )
@login_required
def upload_lead_document(request, lead_id):
    lead = get_object_or_404(Lead, lead_id=lead_id)

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("lead_detail", lead_id=lead.lead_id)

        LeadDocument.objects.create(
            lead=lead,
            file=uploaded_file,
            original_name=uploaded_file.name,
            file_size=uploaded_file.size,
            uploaded_by=request.user,
        )

        messages.success(request, "Document uploaded successfully.")

    return redirect("lead_detail", lead_id=lead.lead_id)

@login_required
def delete_lead_document(request, document_id):
    document = get_object_or_404(
        LeadDocument,
        id=document_id
    )

    lead = document.lead

    if request.method == "POST":
        # Delete the physical file from media storage
        if document.file:
            document.file.delete(save=False)

        # Delete the database record
        document.delete()

        messages.success(
            request,
            "Document deleted successfully."
        )

    return redirect(
        "lead_detail",
        lead_id=lead.lead_id
    )

@login_required
def add_activity(request, lead_id):

    lead = get_object_or_404(
        Lead,
        lead_id=lead_id
    )

    if request.method != "POST":
        messages.error(
            request,
            "Invalid request."
        )
        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    activity_type = request.POST.get(
        "activity_type",
        ""
    ).strip()

    description = request.POST.get(
        "description",
        ""
    ).strip()

    # ---------------------------------------------------------
    # VALID ACTIVITY TYPES
    # ---------------------------------------------------------

    allowed_activity_types = dict(
        LeadActivity.ActivityType.choices
    )

    if activity_type not in allowed_activity_types:

        messages.error(
            request,
            "Please select a valid activity type."
        )

        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    # ---------------------------------------------------------
    # DESCRIPTION VALIDATION
    # ---------------------------------------------------------

    if not description:

        messages.error(
            request,
            "Please describe what happened."
        )

        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    # ---------------------------------------------------------
    # CREATE ACTIVITY
    # ---------------------------------------------------------

    activity = LeadActivity.objects.create(
        lead=lead,
        activity_type=activity_type,
        description=description,
        created_by=request.user,
    )

    # ---------------------------------------------------------
    # UPDATE LEAD'S LAST ACTIVITY TIME
    # ---------------------------------------------------------

    lead.updated_at = timezone.now()

    lead.save(
        update_fields=[
            "updated_at"
        ]
    )

    # ---------------------------------------------------------
    # SUCCESS MESSAGE
    # ---------------------------------------------------------

    activity_label = allowed_activity_types.get(
        activity_type,
        activity_type
    )

    messages.success(
        request,
        f"{activity_label} activity added successfully."
    )

    return redirect(
        "lead_detail",
        lead_id=lead.lead_id
    )
@login_required
def add_follow_up(request, lead_id):
    lead = get_object_or_404(Lead, lead_id=lead_id)
    User = get_user_model()

    if request.user.role in ["ADMIN", "MANAGER"]:
        sales_users = User.objects.filter(
            role=User.Role.SALES,
            is_active=True
        ).order_by("username")
    else:
        sales_users = User.objects.filter(
            id=request.user.id,
            role=User.Role.SALES,
            is_active=True
        )

    # Default form values
    form_data = {
        "title": "",
        "description": "",
        "due_date": "",
        "due_time": "",
        "priority": LeadTask.Priority.MEDIUM,
        "assigned_to": "",
    }

    if request.method == "POST":

        # Keep all values entered by the user
        form_data = {
            "title": request.POST.get("title", "").strip(),
            "description": request.POST.get("description", "").strip(),
            "due_date": request.POST.get("due_date", "").strip(),
            "due_time": request.POST.get("due_time", "").strip(),
            "priority": request.POST.get(
                "priority",
                LeadTask.Priority.MEDIUM
            ).strip(),
            "assigned_to": request.POST.get(
                "assigned_to",
                ""
            ).strip(),
        }

        title = form_data["title"]
        description = form_data["description"]
        due_date = form_data["due_date"]
        due_time = form_data["due_time"]
        priority = form_data["priority"]
        assigned_to_id = form_data["assigned_to"]

        # -----------------------------
        # REQUIRED FIELD VALIDATION
        # -----------------------------

        if not title or not due_date or not due_time:

            messages.error(
                request,
                "Title, due date and due time are required."
            )

            return render(
                request,
                "leads/follow_up_form.html",
                {
                    "lead": lead,
                    "sales_users": sales_users,
                    "priority_choices": LeadTask.Priority.choices,
                    "form_data": form_data,
                }
            )

        # -----------------------------
        # PRIORITY VALIDATION
        # -----------------------------

        valid_priorities = {
            choice[0]
            for choice in LeadTask.Priority.choices
        }

        if priority not in valid_priorities:

            messages.error(
                request,
                "Please select a valid priority."
            )

            return render(
                request,
                "leads/follow_up_form.html",
                {
                    "lead": lead,
                    "sales_users": sales_users,
                    "priority_choices": LeadTask.Priority.choices,
                    "form_data": form_data,
                }
            )

        # -----------------------------
        # DATE + TIME VALIDATION
        # -----------------------------

        try:

            due_datetime = timezone.datetime.strptime(
                f"{due_date} {due_time}",
                "%Y-%m-%d %H:%M"
            )

            due_datetime = timezone.make_aware(
                due_datetime,
                timezone.get_current_timezone()
            )

        except ValueError:

            messages.error(
                request,
                "Please enter a valid date and time."
            )

            return render(
                request,
                "leads/follow_up_form.html",
                {
                    "lead": lead,
                    "sales_users": sales_users,
                    "priority_choices": LeadTask.Priority.choices,
                    "form_data": form_data,
                }
            )

        # -----------------------------
        # FUTURE DATE VALIDATION
        # -----------------------------

        if due_datetime <= timezone.now():

            messages.error(
                request,
                "Follow-up date and time must be in the future."
            )

            return render(
                request,
                "leads/follow_up_form.html",
                {
                    "lead": lead,
                    "sales_users": sales_users,
                    "priority_choices": LeadTask.Priority.choices,
                    "form_data": form_data,
                }
            )

        # -----------------------------
        # ASSIGNMENT VALIDATION
        # -----------------------------

        if request.user.role in ["ADMIN", "MANAGER"]:

            assigned_user = User.objects.filter(
                id=assigned_to_id,
                role=User.Role.SALES,
                is_active=True
            ).first()

            if not assigned_user:

                messages.error(
                    request,
                    "Please select a valid Sales Employee."
                )

                return render(
                    request,
                    "leads/follow_up_form.html",
                    {
                        "lead": lead,
                        "sales_users": sales_users,
                        "priority_choices": LeadTask.Priority.choices,
                        "form_data": form_data,
                    }
                )

        else:

            assigned_user = request.user

        # -----------------------------
        # DUPLICATE PENDING FOLLOW-UP CHECK
        # -----------------------------

        duplicate_task = LeadTask.objects.filter(
            lead=lead,
            title__iexact=title,
            assigned_to=assigned_user,
            status=LeadTask.Status.PENDING,
            due_date=due_datetime,
        ).first()

        if duplicate_task:

            messages.warning(
                request,
                "A pending follow-up with the same title, "
                "employee and due time already exists."
            )

            return redirect(
                "lead_detail",
                lead_id=lead.lead_id
            )

        # -----------------------------
        # CREATE FOLLOW-UP
        # -----------------------------

        from django.db import transaction

        with transaction.atomic():

            task = LeadTask.objects.create(
                lead=lead,
                title=title,
                description=description,
                assigned_to=assigned_user,
                due_date=due_datetime,
                priority=priority,
            )

            # Update next follow-up on lead
            lead.next_follow_up = due_datetime

            lead.save(
                update_fields=[
                    "next_follow_up",
                    "updated_at"
                ]
            )

            # Add timeline activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type=LeadActivity.ActivityType.FOLLOW_UP,
                description=f"Follow-up scheduled: {title}",
                created_by=request.user,
            )

        messages.success(
            request,
            "Follow-up scheduled successfully."
        )

        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    # -----------------------------
    # GET REQUEST
    # -----------------------------

    return render(
        request,
        "leads/follow_up_form.html",
        {
            "lead": lead,
            "sales_users": sales_users,
            "priority_choices": LeadTask.Priority.choices,
            "form_data": form_data,
        }
    )
@login_required
def update_lead_notes(request, lead_id):
    lead = get_object_or_404(Lead, lead_id=lead_id)

    # Sales Employee can edit notes only for their assigned lead
    if request.user.role == "SALES" and lead.assigned_to != request.user:
        messages.error(request, "You are not allowed to update this lead.")
        return redirect("lead_detail", lead_id=lead.lead_id)

    if request.method == "POST":
        notes = request.POST.get("notes", "").strip()

        lead.notes = notes
        lead.save(update_fields=["notes", "updated_at"])

        messages.success(request, "Notes updated successfully.")
        return redirect("lead_detail", lead_id=lead.lead_id)

    return redirect("lead_detail", lead_id=lead.lead_id)
@login_required
def follow_up_list(request):
    """
    Display pending follow-ups grouped by urgency.

    Admin/Manager:
        See team follow-ups.

    Sales Employee:
        See only their assigned follow-ups.

    Groups:
        - Overdue
        - Today
        - Upcoming
    """

    if request.user.role in ["ADMIN", "MANAGER"]:
        tasks = LeadTask.objects.filter(
            status=LeadTask.Status.PENDING
        )
    else:
        tasks = LeadTask.objects.filter(
            status=LeadTask.Status.PENDING,
            assigned_to=request.user
        )

    tasks = tasks.select_related(
        "lead",
        "assigned_to"
    ).order_by("due_date")

    now = timezone.now()
    today = timezone.localdate()

    today_start = timezone.make_aware(
        timezone.datetime.combine(
            today,
            timezone.datetime.min.time()
        ),
        timezone.get_current_timezone()
    )

    tomorrow_start = today_start + timezone.timedelta(days=1)

    # Anything whose exact due time has already passed
    # is overdue, including tasks due earlier today.
    overdue_tasks = tasks.filter(
        due_date__lt=now
    )

    # Remaining tasks scheduled for later today.
    today_tasks = tasks.filter(
        due_date__gte=now,
        due_date__lt=tomorrow_start
    )

    # Tasks scheduled from tomorrow onwards.
    upcoming_tasks = tasks.filter(
        due_date__gte=tomorrow_start
    )

    context = {
        "overdue_tasks": overdue_tasks,
        "today_tasks": today_tasks,
        "upcoming_tasks": upcoming_tasks,

        "total_followups": tasks.count(),
        "overdue_count": overdue_tasks.count(),
        "today_count": today_tasks.count(),
        "upcoming_count": upcoming_tasks.count(),
    }

    return render(
        request,
        "leads/follow_up_list.html",
        context
    )
@login_required
def complete_task(request, task_id):

    # Only POST requests can complete a task.
    if request.method != "POST":
        messages.error(
            request,
            "Invalid request."
        )
        return redirect("follow_up_list")

    task = get_object_or_404(
        LeadTask,
        id=task_id
    )

    # Sales employees can complete only their own tasks.
    if request.user.role == "SALES" and task.assigned_to != request.user:
        messages.error(
            request,
            "You are not allowed to complete this task."
        )
        return redirect("follow_up_list")

    # Only pending tasks can be completed.
    if task.status != LeadTask.Status.PENDING:
        messages.warning(
            request,
            "This task is already completed or cancelled."
        )
        return redirect("follow_up_list")

    # Mark task as completed.
    task.status = LeadTask.Status.COMPLETED
    task.save()

    messages.success(
        request,
        f"Task '{task.title}' completed successfully."
    )

    return redirect("follow_up_list")

@login_required
def pipeline(request):
    from datetime import datetime, time

    from django.contrib.auth import get_user_model
    from django.db.models import Q, Sum
    from django.utils import timezone

    # -----------------------------
    # BASE LEAD QUERY
    # -----------------------------
    if request.user.role in ["ADMIN", "MANAGER"]:
        leads = Lead.objects.select_related(
            "assigned_to"
        ).all()
    else:
        leads = Lead.objects.select_related(
            "assigned_to"
        ).filter(
            assigned_to=request.user
        )

    # -----------------------------
    # GET FILTER VALUES
    # -----------------------------
    search = request.GET.get(
        "q", ""
    ).strip()

    selected_stage = request.GET.get(
        "stage", ""
    ).strip().upper()

    selected_temperature = request.GET.get(
        "temperature", ""
    ).strip().upper()

    selected_priority = request.GET.get(
        "priority", ""
    ).strip().upper()

    selected_assigned_to = request.GET.get(
        "assigned_to", ""
    ).strip()

    min_value = request.GET.get(
        "min_value", ""
    ).strip()

    max_value = request.GET.get(
        "max_value", ""
    ).strip()

    from_date = request.GET.get(
        "from_date", ""
    ).strip()

    to_date = request.GET.get(
        "to_date", ""
    ).strip()

    # -----------------------------
    # SEARCH FILTER
    # -----------------------------
    if search:
        leads = leads.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(company__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(lead_id__icontains=search)
        )

    # -----------------------------
    # STAGE FILTER
    # -----------------------------
    if selected_stage:
        leads = leads.filter(
            status=selected_stage
        )

    # -----------------------------
    # TEMPERATURE FILTER
    # -----------------------------
    if selected_temperature:
        leads = leads.filter(
            temperature=selected_temperature
        )

    # -----------------------------
    # PRIORITY FILTER
    # -----------------------------
    if selected_priority:
        leads = leads.filter(
            priority=selected_priority
        )

    # -----------------------------
    # ASSIGNED TO FILTER
    # -----------------------------
    if selected_assigned_to:
        leads = leads.filter(
            assigned_to_id=selected_assigned_to
        )

    # -----------------------------
    # VALUE FILTER
    # -----------------------------
    if min_value:
        leads = leads.filter(
            lead_value__gte=min_value
        )

    if max_value:
        leads = leads.filter(
            lead_value__lte=max_value
        )

    # -----------------------------
    # CREATED DATE FILTER
    # FILTER BY LEAD CREATED_AT
    # -----------------------------
    if from_date:
        try:
            from_date_obj = datetime.strptime(
                from_date,
                "%Y-%m-%d"
            ).date()

            from_datetime = timezone.make_aware(
                datetime.combine(
                    from_date_obj,
                    time.min
                )
            )

            leads = leads.filter(
                created_at__gte=from_datetime
            )

        except ValueError:
            from_date = ""

    if to_date:
        try:
            to_date_obj = datetime.strptime(
                to_date,
                "%Y-%m-%d"
            ).date()

            to_datetime = timezone.make_aware(
                datetime.combine(
                    to_date_obj,
                    time.max
                )
            )

            leads = leads.filter(
                created_at__lte=to_datetime
            )

        except ValueError:
            to_date = ""

    # -----------------------------
    # PIPELINE STAGES
    # -----------------------------
    pipeline_stages = [
        Lead.Status.NEW,
        Lead.Status.CONTACTED,
        Lead.Status.QUALIFIED,
        Lead.Status.PROPOSAL,
        Lead.Status.NEGOTIATION,
        Lead.Status.WON,
        Lead.Status.LOST,
    ]

    pipeline = {}

    for stage in pipeline_stages:

        stage_leads = leads.filter(
            status=stage
        )

        stage_value = (
            stage_leads.aggregate(
                total=Sum("lead_value")
            )["total"]
            or 0
        )

        pipeline[stage] = {
            "label": dict(
                Lead.Status.choices
            ).get(
                stage,
                stage
            ),
            "leads": stage_leads,
            "count": stage_leads.count(),
            "value": stage_value,
        }

    # -----------------------------
    # SUMMARY CARDS
    # -----------------------------
    total_leads = leads.count()

    total_value = (
        leads.aggregate(
            total=Sum("lead_value")
        )["total"]
        or 0
    )

    hot_leads = leads.filter(
        temperature=Lead.Temperature.HOT
    ).count()

    open_leads = leads.exclude(
        status__in=[
            Lead.Status.WON,
            Lead.Status.LOST,
        ]
    ).count()

    # -----------------------------
    # EMPLOYEES
    # -----------------------------
    User = get_user_model()

    employees = User.objects.filter(
        is_active=True
    ).order_by(
        "first_name",
        "last_name",
        "username"
    )

    # -----------------------------
    # CONTEXT
    # -----------------------------
    context = {
        "pipeline": pipeline,
        "pipeline_stages": pipeline_stages,

        "total_leads": total_leads,
        "total_value": total_value,
        "hot_leads": hot_leads,
        "open_leads": open_leads,

        "employees": employees,

        "search": search,
        "selected_stage": selected_stage,
        "selected_temperature": selected_temperature,
        "selected_priority": selected_priority,
        "selected_assigned_to": selected_assigned_to,

        "min_value": min_value,
        "max_value": max_value,

        "from_date": from_date,
        "to_date": to_date,

        "status_choices": Lead.Status.choices,
        "temperature_choices": Lead.Temperature.choices,
        "priority_choices": Lead.Priority.choices,
    }

    return render(
        request,
        "leads/pipeline.html",
        context
    )

@login_required
def my_work_today(request):
    today = timezone.localdate()
    now = timezone.now()

    # ---------------------------------------------------------
    # BASE LEADS AND TASKS
    # ---------------------------------------------------------

    # Admin and Manager can see all leads and tasks.
    # Sales Employee can see only their assigned leads and tasks.
    if request.user.role in ["ADMIN", "MANAGER"]:

        leads = Lead.objects.select_related(
            "assigned_to"
        ).all()

        tasks = LeadTask.objects.select_related(
            "lead",
            "assigned_to"
        ).all()

    else:

        leads = Lead.objects.select_related(
            "assigned_to"
        ).filter(
            assigned_to=request.user
        )

        tasks = LeadTask.objects.select_related(
            "lead",
            "assigned_to"
        ).filter(
            assigned_to=request.user
        )

    # ---------------------------------------------------------
    # PENDING FOLLOW-UP TASKS
    # ---------------------------------------------------------

    pending_tasks = tasks.filter(
        status=LeadTask.Status.PENDING
    ).order_by(
        "due_date"
    )

    # ---------------------------------------------------------
    # TODAY'S FOLLOW-UPS
    # ---------------------------------------------------------

    todays_followups = pending_tasks.filter(
        due_date__date=today
    ).order_by(
        "due_date"
    )

    # ---------------------------------------------------------
    # OVERDUE FOLLOW-UPS
    # ---------------------------------------------------------

    overdue_followups = pending_tasks.filter(
        due_date__lt=now
    ).order_by(
        "due_date"
    )

    # ---------------------------------------------------------
    # NEW LEADS
    # ---------------------------------------------------------

    new_leads = leads.filter(
        status=Lead.Status.NEW
    ).order_by(
        "-created_at"
    )

    # ---------------------------------------------------------
    # HOT LEADS
    # ---------------------------------------------------------
    # Only active Hot Leads are shown.
    # Won and Lost leads are excluded.
    # ---------------------------------------------------------

    hot_leads = leads.filter(
        temperature=Lead.Temperature.HOT
    ).exclude(
        status__in=[
            Lead.Status.WON,
            Lead.Status.LOST
        ]
    ).order_by(
        "-updated_at"
    )

    # ---------------------------------------------------------
    # OVERDUE TASKS
    # ---------------------------------------------------------

    overdue_tasks = pending_tasks.filter(
        due_date__lt=now
    )

    # ---------------------------------------------------------
    # TODAY'S COMPLETED TASKS
    # ---------------------------------------------------------

    completed_tasks_today = tasks.filter(
        status=LeadTask.Status.COMPLETED,
        completed_at__date=today
    ).order_by(
        "-completed_at"
    )

    # ---------------------------------------------------------
    # RENDER
    # ---------------------------------------------------------

    context = {
        "todays_followups": todays_followups,
        "overdue_followups": overdue_followups,

        "new_leads": new_leads,
        "hot_leads": hot_leads,

        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
        "completed_tasks_today": completed_tasks_today,
    }

    return render(
        request,
        "leads/my_work_today.html",
        context
    )




@login_required
def lead_inbox(request):
    """
    Production Lead Inbox.

    Admin / Manager:
        Can see all New leads.

    Sales Employee:
        Can see only New leads assigned to them.

    Inbox provides:
        - New lead count
        - Hot lead count
        - High priority count
        - Scheduled follow-up count
        - Today's follow-up count
        - Overdue follow-up count
        - Search
        - Temperature filter
        - Priority filter
        - Overdue follow-up filter
        - Follow-up status for every lead
    """

    from django.db.models import Q
    from django.utils import timezone

    # ---------------------------------------------------------
    # CURRENT DATE / TIME
    # ---------------------------------------------------------

    now = timezone.now()
    today = timezone.localdate()

    # ---------------------------------------------------------
    # BASE QUERYSET FOR COUNTS
    # ---------------------------------------------------------

    if request.user.role in ["ADMIN", "MANAGER"]:
        count_base = Lead.objects.filter(
            status=Lead.Status.NEW
        )
    else:
        count_base = Lead.objects.filter(
            status=Lead.Status.NEW,
            assigned_to=request.user
        )

    # ---------------------------------------------------------
    # COUNTS
    # ---------------------------------------------------------

    new_leads_count = count_base.count()

    hot_leads_count = count_base.filter(
        temperature=Lead.Temperature.HOT
    ).count()

    high_priority_count = count_base.filter(
        priority=Lead.Priority.HIGH
    ).count()

    # ---------------------------------------------------------
    # FOLLOW-UP COUNTS
    # ---------------------------------------------------------

    scheduled_followups_count = count_base.filter(
        next_follow_up__isnull=False
    ).count()

    todays_followups_count = count_base.filter(
        next_follow_up__date=today
    ).count()

    overdue_followups_count = count_base.filter(
        next_follow_up__lt=now
    ).count()

    # ---------------------------------------------------------
    # INBOX QUERYSET
    # ---------------------------------------------------------

    inbox_leads = Lead.objects.select_related(
        "assigned_to"
    ).filter(
        status=Lead.Status.NEW
    )

    # Sales employees can see only their assigned leads.
    if request.user.role == "SALES":
        inbox_leads = inbox_leads.filter(
            assigned_to=request.user
        )

    # ---------------------------------------------------------
    # SEARCH FILTER
    # ---------------------------------------------------------

    search = request.GET.get(
        "search",
        ""
    ).strip()

    if search:
        inbox_leads = inbox_leads.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(company__icontains=search)
            | Q(lead_id__icontains=search)
        )

    # ---------------------------------------------------------
    # TEMPERATURE FILTER
    # ---------------------------------------------------------

    temperature_filter = request.GET.get(
        "temperature",
        ""
    ).strip()

    if temperature_filter in dict(
        Lead.Temperature.choices
    ):
        inbox_leads = inbox_leads.filter(
            temperature=temperature_filter
        )

    # ---------------------------------------------------------
    # PRIORITY FILTER
    # ---------------------------------------------------------

    priority_filter = request.GET.get(
        "priority",
        ""
    ).strip()

    if priority_filter in dict(
        Lead.Priority.choices
    ):
        inbox_leads = inbox_leads.filter(
            priority=priority_filter
        )

    # ---------------------------------------------------------
    # FOLLOW-UP STATUS FILTER
    # ---------------------------------------------------------

    followup_filter = request.GET.get(
        "followup",
        ""
    ).strip().upper()

    if followup_filter == "OVERDUE":
        inbox_leads = inbox_leads.filter(
            next_follow_up__lt=now
        )

    # ---------------------------------------------------------
    # ORDER
    # ---------------------------------------------------------

    leads = inbox_leads.order_by(
        "-created_at"
    )

    # ---------------------------------------------------------
    # FOLLOW-UP STATE
    #
    # NONE
    # TODAY
    # OVERDUE
    # UPCOMING
    # ---------------------------------------------------------

    for lead in leads:
        if not lead.next_follow_up:
            lead.followup_state = "NONE"

        elif lead.next_follow_up < now:
            lead.followup_state = "OVERDUE"

        elif lead.next_follow_up.date() == today:
            lead.followup_state = "TODAY"

        else:
            lead.followup_state = "UPCOMING"

    # ---------------------------------------------------------
    # CONTEXT
    # ---------------------------------------------------------

    context = {
        "leads": leads,

        # Summary counts
        "new_leads_count": new_leads_count,
        "hot_leads_count": hot_leads_count,
        "high_priority_count": high_priority_count,

        # Follow-up counts
        "follow_up_count": scheduled_followups_count,
        "scheduled_followups_count": scheduled_followups_count,
        "todays_followups_count": todays_followups_count,
        "overdue_followups_count": overdue_followups_count,

        # Filters
        "search": search,
        "temperature_filter": temperature_filter,
        "priority_filter": priority_filter,
        "followup_filter": followup_filter,

        # Filter choices
        "temperature_choices": Lead.Temperature.choices,
        "priority_choices": Lead.Priority.choices,
    }

    return render(
        request,
        "leads/lead_inbox.html",
        context
    )

@login_required
def convert_lead_to_customer(request, lead_id):

    if request.method != "POST":
        messages.error(
            request,
            "Invalid request."
        )
        return redirect(
            "lead_detail",
            lead_id=lead_id
        )

    lead = get_object_or_404(
        Lead,
        lead_id=lead_id
    )

    # Only Won leads can be converted.
    if lead.status != Lead.Status.WON:
        messages.error(
            request,
            "Only Won leads can be converted into customers."
        )
        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    # Check whether this lead is already converted.
    if hasattr(lead, "customer"):
        messages.warning(
            request,
            "This lead has already been converted into a customer."
        )
        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    # Create customer from lead information.
    customer = Customer.objects.create(
        first_name=lead.first_name,
        last_name=lead.last_name,
        phone=lead.phone,
        whatsapp_number=lead.whatsapp_number,
        email=lead.email,
        company=lead.company,
        source=lead.source,
        assigned_to=lead.assigned_to,
        lead=lead,
    )

    # Record conversion in lead timeline.
    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.NOTE,
        description=(
            f"Lead converted to customer "
            f"{customer.customer_id}."
        ),
        created_by=request.user,
    )

    messages.success(
        request,
        f"{lead.lead_id} converted successfully to "
        f"{customer.customer_id}."
    )

    return redirect(
        "lead_detail",
        lead_id=lead.lead_id
    )

@login_required
def customer_list(request):

    # Admin and Manager can see all active customers.
    if request.user.role in ["ADMIN", "MANAGER"]:
        customers = Customer.objects.select_related(
            "assigned_to"
        ).filter(
            status=Customer.Status.ACTIVE
        )

    # Sales Employee can see only their active customers.
    else:
        customers = Customer.objects.select_related(
            "assigned_to"
        ).filter(
            assigned_to=request.user,
            status=Customer.Status.ACTIVE
        )

    customers = customers.order_by("-created_at")

    return render(
        request,
        "leads/customer_list.html",
        {
            "customers": customers,
        },
    )
@login_required
def customer_detail(request, customer_id):

    # Admin and Manager can view any active customer.
    if request.user.role in ["ADMIN", "MANAGER"]:
        customer = get_object_or_404(
            Customer.objects.select_related("assigned_to"),
            customer_id=customer_id,
            status=Customer.Status.ACTIVE,
        )

    # Sales Employee can view only their own active customers.
    else:
        customer = get_object_or_404(
            Customer.objects.select_related("assigned_to"),
            customer_id=customer_id,
            assigned_to=request.user,
            status=Customer.Status.ACTIVE,
        )

    return render(
        request,
        "leads/customer_detail.html",
        {
            "customer": customer,
        },
    )

@login_required
def deal_list(request):

    # Admin and Manager can see all deals.
    if request.user.role in ["ADMIN", "MANAGER"]:
        deals = Deal.objects.select_related(
            "customer",
            "customer__lead",
            "assigned_to"
        ).all()

    # Sales Employee can see only their deals.
    else:
        deals = Deal.objects.select_related(
            "customer",
            "customer__lead",
            "assigned_to"
        ).filter(
            assigned_to=request.user
        )

    deals = deals.order_by("-created_at")

    return render(
        request,
        "leads/deal_list.html",
        {
            "deals": deals,
        },
    )


@login_required
def deal_detail(request, deal_id):

    if request.user.role in ["ADMIN", "MANAGER"]:
        deal = get_object_or_404(
            Deal.objects.select_related(
                "customer",
                "assigned_to"
            ),
            deal_id=deal_id
        )
    else:
        deal = get_object_or_404(
            Deal.objects.select_related(
                "customer",
                "assigned_to"
            ),
            deal_id=deal_id,
            assigned_to=request.user
        )

    return render(
        request,
        "leads/deal_detail.html",
        {
            "deal": deal,
            "status_choices": Deal.Status.choices,
        },
    )


@login_required
def create_deal(request):

    User = get_user_model()

    if request.method == "POST":

        customer_id = request.POST.get("customer")
        title = request.POST.get("title", "").strip()
        deal_value = request.POST.get("deal_value", 0) or 0

        status = request.POST.get(
            "status",
            Deal.Status.ACTIVE
        )

        expected_close_date = (
            request.POST.get("expected_close_date")
            or None
        )

        notes = request.POST.get(
            "notes",
            ""
        ).strip()

        customer = get_object_or_404(
            Customer,
            id=customer_id
        )

        # Sales employees are automatically assigned
        # to their own deals.
        if request.user.role == "SALES":
            assigned_to = request.user

        # Admin and Manager can select a sales employee.
        else:
            assigned_user_id = request.POST.get(
                "assigned_to"
            )

            assigned_to = User.objects.filter(
                id=assigned_user_id,
                role=User.Role.SALES,
                is_active=True
            ).first()

        deal = Deal.objects.create(
            customer=customer,
            title=title,
            deal_value=deal_value,
            status=status,
            expected_close_date=expected_close_date,
            assigned_to=assigned_to,
            notes=notes,
        )

        messages.success(
            request,
            f"{deal.deal_id} created successfully."
        )

        return redirect("deal_list")

    # Admin and Manager can assign deals.
    if request.user.role in ["ADMIN", "MANAGER"]:

        sales_users = User.objects.filter(
            role=User.Role.SALES,
            is_active=True
        ).order_by("username")

    else:
        sales_users = []

    # Admin and Manager see all customers.
    if request.user.role in ["ADMIN", "MANAGER"]:

        customers = Customer.objects.all().order_by(
            "first_name"
        )

    else:

        customers = Customer.objects.filter(
            assigned_to=request.user
        ).order_by(
            "first_name"
        )

    return render(
        request,
        "leads/deal_form.html",
        {
            "customers": customers,
            "sales_users": sales_users,
            "status_choices": Deal.Status.choices,
        },
    )



@login_required
def edit_deal(request, deal_id):

    User = get_user_model()

    # Admin and Manager can edit any deal.
    if request.user.role in ["ADMIN", "MANAGER"]:

        deal = get_object_or_404(
            Deal,
            deal_id=deal_id
        )

    # Sales Employee can edit only their assigned deals.
    else:

        deal = get_object_or_404(
            Deal,
            deal_id=deal_id,
            assigned_to=request.user
        )


    # ------------------------------------------------
    # UPDATE DEAL
    # ------------------------------------------------
    if request.method == "POST":

        deal.title = request.POST.get(
            "title",
            ""
        ).strip()

        deal.deal_value = request.POST.get(
            "deal_value",
            0
        ) or 0

        deal.expected_close_date = (
            request.POST.get("expected_close_date")
            or None
        )

        deal.notes = request.POST.get(
            "notes",
            ""
        ).strip()


        # ------------------------------------------------
        # ADMIN / MANAGER CAN CHANGE ASSIGNED SALES USER
        # ------------------------------------------------
        if request.user.role in ["ADMIN", "MANAGER"]:

            assigned_user_id = request.POST.get(
                "assigned_to"
            )

            deal.assigned_to = User.objects.filter(
                id=assigned_user_id,
                role=User.Role.SALES,
                is_active=True
            ).first()


        # ------------------------------------------------
        # SAVE
        # ------------------------------------------------
        deal.save()


        messages.success(
            request,
            f"{deal.deal_id} updated successfully."
        )


        return redirect(
            "deal_detail",
            deal_id=deal.deal_id
        )


    # ------------------------------------------------
    # SALES USERS
    # ------------------------------------------------
    if request.user.role in ["ADMIN", "MANAGER"]:

        sales_users = User.objects.filter(
            role=User.Role.SALES,
            is_active=True
        ).order_by("username")

    else:

        sales_users = []


    # ------------------------------------------------
    # EDIT PAGE
    # ------------------------------------------------
    return render(
        request,
        "leads/deal_edit.html",
        {
            "deal": deal,
            "sales_users": sales_users,
        },
    )


@login_required
def change_deal_status(request, deal_id):

    if request.user.role in ["ADMIN", "MANAGER"]:
        deal = get_object_or_404(
            Deal,
            deal_id=deal_id
        )
    else:
        deal = get_object_or_404(
            Deal,
            deal_id=deal_id,
            assigned_to=request.user
        )

    if request.method == "POST":

        new_status = request.POST.get(
            "status"
        )

        if new_status not in dict(Deal.Status.choices):
            messages.error(
                request,
                "Invalid deal status."
            )

            return redirect(
                "deal_detail",
                deal_id=deal.deal_id
            )

        old_status = deal.status

        if old_status == new_status:
            messages.info(
                request,
                "Deal status was not changed."
            )

            return redirect(
                "deal_detail",
                deal_id=deal.deal_id
            )

        deal.status = new_status
        deal.save()

        messages.success(
            request,
            f"{deal.deal_id} status changed successfully."
        )

        return redirect(
            "deal_detail",
            deal_id=deal.deal_id
        )

    return render(
        request,
        "leads/deal_status.html",
        {
            "deal": deal,
            "status_choices": Deal.Status.choices,
        },
    )
@login_required
def notification_list(request):
    notifications = Notification.objects.filter(
        user=request.user
    ).select_related("lead", "task")

    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    return render(
        request,
        "leads/notification_list.html",
        {
            "notifications": notifications,
            "unread_notifications": unread_notifications,
        }
    )

@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])

    if notification.lead:
        return redirect("lead_detail", lead_id=notification.lead.lead_id)

    return redirect("notification_list")

@login_required
def admin_task_list(request):

    # Only Admin and Manager can access the team task page.
    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(
            request,
            "You do not have permission to access team tasks."
        )
        return redirect("dashboard")

    User = get_user_model()

    # ---------------------------------------------------------
    # BASE TASK QUERY
    # ---------------------------------------------------------

    tasks = LeadTask.objects.select_related(
        "lead",
        "assigned_to"
    ).all()

    # ---------------------------------------------------------
    # FILTERS
    # ---------------------------------------------------------

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    assigned_to = request.GET.get("assigned_to", "").strip()
    due_filter = request.GET.get("due", "").strip()

    # Search by task title, description or lead ID
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(lead__lead_id__icontains=search)
        )

    # Status filter
    if status:
        tasks = tasks.filter(status=status)

    # Priority filter
    if priority:
        tasks = tasks.filter(priority=priority)

    # Employee filter
    if assigned_to:
        tasks = tasks.filter(assigned_to_id=assigned_to)

    # Date filter
    now = timezone.now()
    today = timezone.localdate()

    if due_filter == "today":
        tasks = tasks.filter(
            due_date__date=today
        )

    elif due_filter == "overdue":
        tasks = tasks.filter(
            status=LeadTask.Status.PENDING,
            due_date__lt=now
        )

    elif due_filter == "upcoming":
        tasks = tasks.filter(
            status=LeadTask.Status.PENDING,
            due_date__gt=now
        )

    # ---------------------------------------------------------
    # SUMMARY COUNTS
    # ---------------------------------------------------------

    all_tasks = LeadTask.objects.all()

    total_tasks = all_tasks.count()

    pending_count = all_tasks.filter(
        status=LeadTask.Status.PENDING
    ).count()

    completed_count = all_tasks.filter(
        status=LeadTask.Status.COMPLETED
    ).count()

    cancelled_count = all_tasks.filter(
        status=LeadTask.Status.CANCELLED
    ).count()

    due_today_count = all_tasks.filter(
        status=LeadTask.Status.PENDING,
        due_date__date=today
    ).count()

    overdue_count = all_tasks.filter(
        status=LeadTask.Status.PENDING,
        due_date__lt=now
    ).count()

    # ---------------------------------------------------------
    # SALES EMPLOYEES
    # ---------------------------------------------------------

    sales_users = User.objects.filter(
        role=User.Role.SALES,
        is_active=True
    ).order_by("username")

    # ---------------------------------------------------------
    # ORDER
    # ---------------------------------------------------------

    tasks = tasks.order_by(
        "status",
        "due_date"
    )

    return render(
        request,
        "leads/admin_task_list.html",
        {
            "tasks": tasks,

            "total_tasks": total_tasks,
            "pending_count": pending_count,
            "completed_count": completed_count,
            "cancelled_count": cancelled_count,
            "due_today_count": due_today_count,
            "overdue_count": overdue_count,

            "sales_users": sales_users,

            "status_choices": LeadTask.Status.choices,
            "priority_choices": LeadTask.Priority.choices,

            "selected_status": status,
            "selected_priority": priority,
            "selected_assigned_to": assigned_to,
            "selected_due": due_filter,
            "search": search,
        }
    )

@login_required
def create_task(request):

    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(
            request,
            "You do not have permission to create team tasks."
        )
        return redirect("dashboard")

    User = get_user_model()

    sales_users = User.objects.filter(
        role=User.Role.SALES,
        is_active=True
    ).order_by("username")

    leads = Lead.objects.all().order_by("-created_at")

    if request.method == "POST":

        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        lead_id = request.POST.get("lead")
        assigned_to_id = request.POST.get("assigned_to")
        due_date = request.POST.get("due_date")
        priority = request.POST.get(
            "priority",
            LeadTask.Priority.MEDIUM
        )

        if not title:
            messages.error(
                request,
                "Task title is required."
            )

            return render(
                request,
                "leads/create_task.html",
                {
                    "sales_users": sales_users,
                    "leads": leads,
                    "priority_choices": LeadTask.Priority.choices,
                }
            )

        lead = None

        if lead_id:
            lead = Lead.objects.filter(
                id=lead_id
            ).first()

        assigned_to = None

        if assigned_to_id:
            assigned_to = User.objects.filter(
                id=assigned_to_id,
                role=User.Role.SALES,
                is_active=True
            ).first()

        task = LeadTask.objects.create(
            title=title,
            description=description,
            lead=lead,
            assigned_to=assigned_to,
            due_date=due_date,
            priority=priority,
            status=LeadTask.Status.PENDING,
        )

        # Record task assignment history.
        TaskAssignmentHistory.objects.create(
            task=task,
            assigned_to=assigned_to,
            assigned_by=request.user,
        )

        # Create notification for the assigned Sales Employee.
        if assigned_to:
            Notification.objects.create(
                user=assigned_to,
                lead=lead,
                task=task,
                notification_type=Notification.NotificationType.TASK,
                title="New Task Assigned",
                message=(
                    f"You have been assigned the task "
                    f"'{task.title}' by {request.user.username}."
                ),
            )

        messages.success(
            request,
            f"Task '{task.title}' created successfully."
        )

        return redirect("admin_task_list")

    return render(
        request,
        "leads/create_task.html",
        {
            "sales_users": sales_users,
            "leads": leads,
            "priority_choices": LeadTask.Priority.choices,
        }
    )
@login_required
def task_detail(request, task_id):

    task = get_object_or_404(
        LeadTask.objects.select_related(
            "lead",
            "assigned_to"
        ),
        id=task_id
    )

    # Admin and Manager can view all team tasks.
    # Sales Employee can only view their own tasks.
    if request.user.role == "SALES":
        if task.assigned_to != request.user:
            messages.error(
                request,
                "You do not have permission to view this task."
            )
            return redirect("dashboard")

    # Get task assignment history.
    assignment_history = task.assignment_history.select_related(
        "assigned_to",
        "assigned_by"
    ).order_by("-assigned_at")

    return render(
        request,
        "leads/task_detail.html",
        {
            "task": task,
            "assignment_history": assignment_history,
        }
    )
@login_required
def complete_task(request, task_id):

    task = get_object_or_404(
        LeadTask,
        id=task_id
    )

    # ---------------------------------------------------------
    # PERMISSION CHECK
    # ---------------------------------------------------------

    # Sales Employee can only complete their own tasks.
    if request.user.role == "SALES":
        if task.assigned_to != request.user:
            messages.error(
                request,
                "You do not have permission to complete this task."
            )
            return redirect("dashboard")

    # ---------------------------------------------------------
    # COMPLETE TASK
    # ---------------------------------------------------------

    if task.status == LeadTask.Status.PENDING:

        task.status = LeadTask.Status.COMPLETED
        task.completed_at = timezone.now()

        task.save(
            update_fields=[
                "status",
                "completed_at"
            ]
        )

        # -----------------------------------------------------
        # UPDATE LEAD NEXT FOLLOW-UP
        # -----------------------------------------------------

        if task.lead:

            # Find the next pending follow-up for this lead.
            next_pending_task = LeadTask.objects.filter(
                lead=task.lead,
                status=LeadTask.Status.PENDING,
                due_date__isnull=False
            ).exclude(
                id=task.id
            ).order_by(
                "due_date"
            ).first()

            if next_pending_task:

                # Another pending follow-up exists.
                task.lead.next_follow_up = next_pending_task.due_date
                task.lead.save(
                    update_fields=[
                        "next_follow_up"
                    ]
                )

            else:

                # No pending follow-up remains.
                task.lead.next_follow_up = None
                task.lead.save(
                    update_fields=[
                        "next_follow_up"
                    ]
                )

        messages.success(
            request,
            f"Task '{task.title}' marked as completed."
        )

    else:

        messages.info(
            request,
            "This task is already completed or cancelled."
        )

    return redirect(
        "task_detail",
        task_id=task.id
    )

@login_required
def cancel_task(request, task_id):

    task = get_object_or_404(
        LeadTask,
        id=task_id
    )

    # Sales Employee can only cancel their own tasks.
    if request.user.role == "SALES":
        if task.assigned_to != request.user:
            messages.error(
                request,
                "You do not have permission to cancel this task."
            )
            return redirect("dashboard")

    if task.status == LeadTask.Status.PENDING:

        task.status = LeadTask.Status.CANCELLED
        task.save(
            update_fields=["status"]
        )

        messages.success(
            request,
            f"Task '{task.title}' cancelled successfully."
        )

    else:
        messages.info(
            request,
            "Only pending tasks can be cancelled."
        )

    return redirect(
        "task_detail",
        task_id=task.id
    )

@login_required
def reassign_task(request, task_id):

    # Only Admin and Manager can reassign tasks.
    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(
            request,
            "You do not have permission to reassign tasks."
        )
        return redirect("dashboard")

    task = get_object_or_404(
        LeadTask,
        id=task_id
    )

    User = get_user_model()

    sales_users = User.objects.filter(
        role=User.Role.SALES,
        is_active=True
    ).order_by("username")

    if request.method == "POST":

        assigned_to_id = request.POST.get("assigned_to")

        assigned_to = User.objects.filter(
            id=assigned_to_id,
            role=User.Role.SALES,
            is_active=True
        ).first()

        if not assigned_to:
            messages.error(
                request,
                "Please select a valid Sales Employee."
            )
            return redirect(
                "task_detail",
                task_id=task.id
            )

        # Prevent assigning the task to the same employee.
        if task.assigned_to == assigned_to:
            messages.info(
                request,
                f"This task is already assigned to {assigned_to.username}."
            )
            return redirect(
                "task_detail",
                task_id=task.id
            )

        old_assigned_to = task.assigned_to

        # Update the task assignment.
        task.assigned_to = assigned_to
        task.save(
            update_fields=["assigned_to"]
        )

        # Record the reassignment history.
        TaskAssignmentHistory.objects.create(
            task=task,
            assigned_to=assigned_to,
            assigned_by=request.user,
        )

        # Notify the new Sales Employee.
        Notification.objects.create(
            user=assigned_to,
            lead=task.lead,
            task=task,
            notification_type=Notification.NotificationType.TASK,
            title="Task Reassigned",
            message=(
                f"You have been assigned the task "
                f"'{task.title}' by {request.user.username}."
            ),
        )

        messages.success(
            request,
            f"Task '{task.title}' reassigned to {assigned_to.username}."
        )

        return redirect(
            "task_detail",
            task_id=task.id
        )

    return render(
        request,
        "leads/reassign_task.html",
        {
            "task": task,
            "sales_users": sales_users,
        }
    )

@login_required
def admin_reports(request):

    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(
            request,
            "You do not have permission to access reports."
        )
        return redirect("dashboard")


    # =========================
    # Pipeline Overview
    # =========================

    total_leads = Lead.objects.count()

    new_leads = Lead.objects.filter(
        status=Lead.Status.NEW
    ).count()

    contacted_leads = Lead.objects.filter(
        status=Lead.Status.CONTACTED
    ).count()

    qualified_leads = Lead.objects.filter(
        status=Lead.Status.QUALIFIED
    ).count()

    proposal_leads = Lead.objects.filter(
        status=Lead.Status.PROPOSAL
    ).count()

    negotiation_leads = Lead.objects.filter(
        status=Lead.Status.NEGOTIATION
    ).count()

    won_leads = Lead.objects.filter(
        status=Lead.Status.WON
    ).count()

    lost_leads = Lead.objects.filter(
        status=Lead.Status.LOST
    ).count()


    # =========================
    # Leads by Source
    # =========================

    lead_source_report = []

    for source_value, source_label in Lead.Source.choices:

        count = Lead.objects.filter(
            source=source_value
        ).count()

        lead_source_report.append({
            "value": source_value,
            "label": source_label,
            "count": count,
        })


    # =========================
    # Sales Employee Performance
    # =========================

    User = get_user_model()

    sales_users = User.objects.filter(
        role=User.Role.SALES,
        is_active=True
    ).order_by("username")

    sales_performance = []

    for user in sales_users:

        assigned_leads = Lead.objects.filter(
            assigned_to=user
        )

        assigned_tasks = LeadTask.objects.filter(
            assigned_to=user
        )

        sales_performance.append({
            "user": user,
            "user_id": user.id,

            "total_leads": assigned_leads.count(),

            "new_leads": assigned_leads.filter(
                status=Lead.Status.NEW
            ).count(),

            "won_leads": assigned_leads.filter(
                status=Lead.Status.WON
            ).count(),

            "lost_leads": assigned_leads.filter(
                status=Lead.Status.LOST
            ).count(),

            "pending_tasks": assigned_tasks.filter(
                status=LeadTask.Status.PENDING
            ).count(),

            "completed_tasks": assigned_tasks.filter(
                status=LeadTask.Status.COMPLETED
            ).count(),
        })


    # =========================
    # Render Reports Page
    # =========================

    return render(
        request,
        "leads/admin_reports.html",
        {
            # Pipeline
            "total_leads": total_leads,

            "new_leads": new_leads,
            "contacted_leads": contacted_leads,
            "qualified_leads": qualified_leads,
            "proposal_leads": proposal_leads,
            "negotiation_leads": negotiation_leads,
            "won_leads": won_leads,
            "lost_leads": lost_leads,

            # Sources
            "lead_source_report": lead_source_report,

            # Sales Performance
            "sales_performance": sales_performance,
        }
    )
import re

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render

from PIL import Image

from .models import CompanySettings


@login_required
def admin_settings(request):

    # ---------------------------------------------
    # ACCESS CONTROL
    # ---------------------------------------------
    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(
            request,
            "You do not have permission to access settings."
        )
        return redirect("dashboard")

    # ---------------------------------------------
    # GET COMPANY SETTINGS
    # ---------------------------------------------
    settings_obj = CompanySettings.objects.first()

    if not settings_obj:
        settings_obj = CompanySettings.objects.create(
            company_name="My Company"
        )

    # ---------------------------------------------
    # DEFAULT FORM DATA
    # ---------------------------------------------
    form_data = {
        "company_name": settings_obj.company_name,
        "company_email": settings_obj.company_email,
        "company_phone": settings_obj.company_phone,
        "company_address": settings_obj.company_address,
        "website": settings_obj.website,
        "timezone": settings_obj.timezone,
        "currency": settings_obj.currency,
        "date_format": settings_obj.date_format,

        "working_hours_start": (
            settings_obj.working_hours_start.strftime("%H:%M")
            if settings_obj.working_hours_start
            else ""
        ),

        "working_hours_end": (
            settings_obj.working_hours_end.strftime("%H:%M")
            if settings_obj.working_hours_end
            else ""
        ),

        "remove_logo": False,
    }

    # ---------------------------------------------
    # POST REQUEST
    # ---------------------------------------------
    if request.method == "POST":

        # -----------------------------------------
        # GET FORM DATA
        # -----------------------------------------
        company_name = request.POST.get(
            "company_name",
            ""
        ).strip()

        company_email = request.POST.get(
            "company_email",
            ""
        ).strip()

        company_phone = request.POST.get(
            "company_phone",
            ""
        ).strip()

        company_address = request.POST.get(
            "company_address",
            ""
        ).strip()

        website = request.POST.get(
            "website",
            ""
        ).strip()

        timezone_value = request.POST.get(
            "timezone",
            "Asia/Kolkata"
        ).strip()

        currency = request.POST.get(
            "currency",
            "INR"
        ).strip()

        date_format = request.POST.get(
            "date_format",
            "DD/MM/YYYY"
        ).strip()

        working_hours_start = request.POST.get(
            "working_hours_start",
            ""
        ).strip()

        working_hours_end = request.POST.get(
            "working_hours_end",
            ""
        ).strip()

        remove_logo = request.POST.get(
            "remove_logo"
        ) == "1"

        new_logo = request.FILES.get(
            "company_logo"
        )

        # -----------------------------------------
        # KEEP USER ENTERED VALUES
        # -----------------------------------------
        form_data = {
            "company_name": company_name,
            "company_email": company_email,
            "company_phone": company_phone,
            "company_address": company_address,
            "website": website,
            "timezone": timezone_value,
            "currency": currency,
            "date_format": date_format,
            "working_hours_start": working_hours_start,
            "working_hours_end": working_hours_end,
            "remove_logo": remove_logo,
        }

        # -----------------------------------------
        # ERROR LIST
        # -----------------------------------------
        errors = []

        # =========================================
        # COMPANY NAME VALIDATION
        # =========================================
        if not company_name:

            errors.append(
                "Company name is required."
            )

        elif len(company_name) < 2:

            errors.append(
                "Company name must contain at least 2 characters."
            )

        elif len(company_name) > 150:

            errors.append(
                "Company name cannot exceed 150 characters."
            )

        # =========================================
        # EMAIL VALIDATION
        # =========================================
        if company_email:

            try:

                validate_email(company_email)

            except ValidationError:

                errors.append(
                    "Please enter a valid company email address."
                )

            else:

                email_pattern = (
                    r"^[A-Za-z0-9._%+-]+"
                    r"@"
                    r"[A-Za-z0-9-]+"
                    r"(\.[A-Za-z0-9-]+)+$"
                )

                if not re.fullmatch(
                    email_pattern,
                    company_email
                ):

                    errors.append(
                        "Please enter a valid email address "
                        "such as name@example.com."
                    )

        # =========================================
        # PHONE VALIDATION
        # =========================================
        if company_phone:

            # Remove spaces, hyphens, + and brackets
            # before checking the actual digits.
            phone_digits = re.sub(
                r"[\s\-+()]",
                "",
                company_phone
            )

            if not phone_digits.isdigit():

                errors.append(
                    "Phone number can contain only numbers, "
                    "spaces, +, hyphens or brackets."
                )

            elif len(phone_digits) != 10:

                errors.append(
                    "Phone number must contain exactly 10 digits."
                )

        # =========================================
        # WEBSITE VALIDATION
        # =========================================
        if website:

            website_pattern = (
                r"^https?://"
                r"([A-Za-z0-9-]+\.)+"
                r"[A-Za-z]{2,}"
                r"([/:?#].*)?$"
            )

            if not re.fullmatch(
                website_pattern,
                website
            ):

                errors.append(
                    "Please enter a valid website URL "
                    "starting with http:// or https://."
                )

        # =========================================
        # TIMEZONE VALIDATION
        # =========================================
        allowed_timezones = {
            value
            for value, label in TIMEZONE_CHOICES
        }

        if timezone_value not in allowed_timezones:

            errors.append(
                "Invalid timezone selected."
            )

        # =========================================
        # CURRENCY VALIDATION
        # =========================================
        allowed_currencies = {
            value
            for value, label in CURRENCY_CHOICES
        }

        if currency not in allowed_currencies:

            errors.append(
                "Invalid currency selected."
            )

        # =========================================
        # DATE FORMAT VALIDATION
        # =========================================
        allowed_date_formats = [
            "DD/MM/YYYY",
            "MM/DD/YYYY",
            "YYYY-MM-DD",
        ]

        if date_format not in allowed_date_formats:

            errors.append(
                "Invalid date format selected."
            )

        # =========================================
        # WORKING HOURS VALIDATION
        # =========================================
        start_time = None
        end_time = None

        if working_hours_start:

            try:

                start_time = datetime.strptime(
                    working_hours_start,
                    "%H:%M"
                ).time()

            except ValueError:

                errors.append(
                    "Invalid working hours start time."
                )

        if working_hours_end:

            try:

                end_time = datetime.strptime(
                    working_hours_end,
                    "%H:%M"
                ).time()

            except ValueError:

                errors.append(
                    "Invalid working hours end time."
                )

        if start_time and end_time:

            if end_time <= start_time:

                errors.append(
                    "Working hours end time must be "
                    "after start time."
                )

        # =========================================
        # LOGO VALIDATION
        # =========================================
        if remove_logo and new_logo:

            errors.append(
                "Choose either remove the current logo "
                "or upload a new logo, not both."
            )

        detected_logo_format = None

        if new_logo:

            # -------------------------------------
            # SIZE VALIDATION
            # -------------------------------------
            if new_logo.size > 2 * 1024 * 1024:

                errors.append(
                    "Company logo must be smaller than 2 MB."
                )

            # -------------------------------------
            # ACTUAL IMAGE VALIDATION
            # -------------------------------------
            else:

                try:

                    image = Image.open(new_logo)

                    detected_logo_format = image.format

                    image.verify()

                except Exception:

                    errors.append(
                        "Please upload a valid image file."
                    )

                finally:

                    try:

                        new_logo.seek(0)

                    except Exception:

                        pass

            # -------------------------------------
            # IMAGE FORMAT
            # -------------------------------------
            if detected_logo_format not in [
                "PNG",
                "JPEG",
                "WEBP",
            ]:

                errors.append(
                    "Only PNG, JPG or WebP images are allowed."
                )

        # =========================================
        # IF ANY ERROR
        # =========================================
        if errors:

            return render(
                request,
                "leads/admin_settings.html",
                {
                    "settings_obj": settings_obj,
                    "form_data": form_data,
                    "settings_errors": errors,
                }
            )

        # =========================================
        # SAVE COMPANY INFORMATION
        # =========================================
        settings_obj.company_name = company_name
        settings_obj.company_email = company_email
        settings_obj.company_phone = company_phone
        settings_obj.company_address = company_address
        settings_obj.website = website
        settings_obj.timezone = timezone_value
        settings_obj.currency = currency
        settings_obj.date_format = date_format

        if start_time:

            settings_obj.working_hours_start = start_time

        if end_time:

            settings_obj.working_hours_end = end_time

        # =========================================
        # LOGO HANDLING
        # =========================================
        if remove_logo:

            if settings_obj.company_logo:

                settings_obj.company_logo.delete(
                    save=False
                )

            settings_obj.company_logo = None

        elif new_logo:

            old_logo = settings_obj.company_logo

            settings_obj.company_logo = new_logo

            settings_obj.save()

            # Delete old logo after successful save
            if old_logo:

                try:

                    old_logo.delete(
                        save=False
                    )

                except Exception:

                    pass

            messages.success(
                request,
                "Company settings updated successfully."
            )

            return redirect(
                "admin_settings"
            )

        # =========================================
        # SAVE SETTINGS
        # =========================================
        settings_obj.save()

        messages.success(
            request,
            "Company settings updated successfully."
        )

        return redirect(
            "admin_settings"
        )

    # =============================================
    # DISPLAY SETTINGS PAGE
    # =============================================
    return render(
        request,
        "leads/admin_settings.html",
        {
            "settings_obj": settings_obj,
            "form_data": form_data,
        }
    )

@login_required
def help_page(request):
    return render(request, "leads/help.html")

@login_required
def report_issue(request):

    if request.method != "POST":
        return redirect("help")

    subject = request.POST.get("subject", "").strip()
    category = request.POST.get("category", "").strip()
    priority = request.POST.get("priority", "").strip()
    description = request.POST.get("description", "").strip()

    # Basic validation
    if not subject:
        messages.error(request, "Please enter an issue title.")
        return redirect("help")

    if category not in dict(SupportTicket.Category.choices):
        messages.error(request, "Please select a valid issue category.")
        return redirect("help")

    if priority not in dict(SupportTicket.Priority.choices):
        messages.error(request, "Please select a valid priority.")
        return redirect("help")

    if not description:
        messages.error(request, "Please describe the issue.")
        return redirect("help")

    # Create support ticket
    with transaction.atomic():

        ticket = SupportTicket.objects.create(
            created_by=request.user,
            subject=subject,
            category=category,
            priority=priority,
            description=description,
        )

    messages.success(
        request,
        f"Support ticket {ticket.ticket_id} has been submitted successfully."
    )

    return redirect("help")

# ============================================================
# LEAD STAGE WORKFLOW
# ============================================================

STAGE_WORKFLOW = {
    "NEW": {
        "number": 1,
        "label": "New",
        "next": "CONTACTED",
        "next_label": "Contacted",
    },
    "CONTACTED": {
        "number": 2,
        "label": "Contacted",
        "next": "QUALIFIED",
        "next_label": "Qualified",
    },
    "QUALIFIED": {
        "number": 3,
        "label": "Qualified",
        "next": "PROPOSAL",
        "next_label": "Proposal",
    },
    "PROPOSAL": {
        "number": 4,
        "label": "Proposal",
        "next": "NEGOTIATION",
        "next_label": "Negotiation",
    },
    "NEGOTIATION": {
        "number": 5,
        "label": "Negotiation",
        "next": "WON",
        "next_label": "Won",
    },
    "WON": {
        "number": 6,
        "label": "Won",
        "next": None,
        "next_label": None,
    },
}


@login_required
def lead_stage(request, lead_id, stage):
    """
    Display and save the form for one lead stage.
    """

    lead = get_object_or_404(
        Lead.objects.select_related("assigned_to"),
        lead_id=lead_id
    )

    # --------------------------------------------------------
    # Permission
    # --------------------------------------------------------

    if request.user.role == "SALES":
        if lead.assigned_to != request.user:
            messages.error(
                request,
                "You are not allowed to update this lead."
            )
            return redirect("lead_list")

    # --------------------------------------------------------
    # Validate stage
    # --------------------------------------------------------

    stage = stage.upper()

    if stage not in STAGE_WORKFLOW:
        messages.error(request, "Invalid lead stage.")
        return redirect("lead_detail", lead_id=lead.lead_id)

    stage_info = STAGE_WORKFLOW[stage]

    # --------------------------------------------------------
    # Stage order
    # --------------------------------------------------------

    stage_order = [
        "NEW",
        "CONTACTED",
        "QUALIFIED",
        "PROPOSAL",
        "NEGOTIATION",
        "WON",
    ]

    current_index = stage_order.index(lead.status)
    requested_index = stage_order.index(stage)

    # Don't allow jumping to a future stage.
    if requested_index > current_index + 1:
        messages.error(
            request,
            "Please complete the previous stage first."
        )
        return redirect(
            "lead_stage",
            lead_id=lead.lead_id,
            stage=lead.status
        )

    # --------------------------------------------------------
    # Existing stage data
    # --------------------------------------------------------

    stage_data = lead.stage_data or {}

    current_data = stage_data.get(stage, {})

    # --------------------------------------------------------
    # POST - Save stage
    # --------------------------------------------------------

    if request.method == "POST":

        # ----------------------------------------------------
        # Collect stage form data
        # ----------------------------------------------------

        data = {}

        for key, value in request.POST.items():

            if key == "csrfmiddlewaretoken":
                continue

            if key == "stage":
                continue

            data[key] = value.strip()

        # ----------------------------------------------------
        # Basic validation
        # ----------------------------------------------------

        if stage == "CONTACTED":

            contact_person = data.get("contact_person", "").strip()
            phone = data.get("contact_phone", "").strip()

            if not contact_person:
                messages.error(
                    request,
                    "Contact person is required."
                )

                return render(
                    request,
                    "leads/lead_stage.html",
                    {
                        "lead": lead,
                        "stage": stage,
                        "stage_info": stage_info,
                        "stage_workflow": STAGE_WORKFLOW,
                        "current_data": data,
                    }
                )

            if not phone:
                messages.error(
                    request,
                    "Phone number is required."
                )

                return render(
                    request,
                    "leads/lead_stage.html",
                    {
                        "lead": lead,
                        "stage": stage,
                        "stage_info": stage_info,
                        "stage_workflow": STAGE_WORKFLOW,
                        "current_data": data,
                    }
                )

        # ----------------------------------------------------
        # Save stage data
        # ----------------------------------------------------

        stage_data[stage] = data

        lead.stage_data = stage_data

        # ----------------------------------------------------
        # Move lead to current stage
        # ----------------------------------------------------

        old_status = lead.status

        lead.status = stage

        lead.save()

        # ----------------------------------------------------
        # Create timeline activity
        # ----------------------------------------------------

        if old_status != stage:

            old_stage_label = dict(
                Lead.Status.choices
            ).get(old_status, old_status)

            new_stage_label = dict(
                Lead.Status.choices
            ).get(stage, stage)

            LeadActivity.objects.create(
                lead=lead,
                activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
                description=(
                    f"Lead moved from "
                    f"{old_stage_label} to "
                    f"{new_stage_label}."
                ),
                created_by=request.user,
            )

        # ----------------------------------------------------
        # If this is the final stage
        # ----------------------------------------------------

        if stage == "WON":

            messages.success(
                request,
                f"{lead.lead_id} has completed the Won stage."
            )

            return redirect(
                "lead_detail",
                lead_id=lead.lead_id
            )

        # ----------------------------------------------------
        # Automatically open next stage
        # ----------------------------------------------------

        next_stage = stage_info["next"]

        messages.success(
            request,
            f"{stage_info['label']} completed. "
            f"Moving to {stage_info['next_label']}."
        )

        return redirect(
            "lead_stage",
            lead_id=lead.lead_id,
            stage=next_stage
        )

    # --------------------------------------------------------
    # GET - Show stage form
    # --------------------------------------------------------

    return render(
        request,
        "leads/lead_stage.html",
        {
            "lead": lead,
            "stage": stage,
            "stage_info": stage_info,
            "stage_workflow": STAGE_WORKFLOW,
            "current_data": current_data,
        }
    )

# ============================================================
# LEAD STAGE WORKFLOW PAGE
# ============================================================

@login_required
def lead_stage_workflow(request, lead_id):

    lead = get_object_or_404(
        Lead.objects.select_related("assigned_to"),
        lead_id=lead_id
    )

    # ========================================================
    # PERMISSION
    # ========================================================

    if (
        request.user.role == "SALES"
        and lead.assigned_to != request.user
    ):
        messages.error(
            request,
            "You are not allowed to update this lead."
        )

        return redirect("lead_list")

    current_status = lead.status

    # ========================================================
    # REQUESTED STAGE
    # ========================================================

    requested_stage = request.GET.get(
        "stage",
        ""
    ).strip().upper()

    # ========================================================
    # SPECIAL CASE: WON -> LOST
    #
    # This MUST come before any STAGE_ORDER.index()
    # because LOST is not part of the normal stage flow.
    #
    # Only Admin can change Won -> Lost.
    # ========================================================

    if (
        current_status == Lead.Status.WON
        and requested_stage == Lead.Status.LOST
    ):

        # ----------------------------------------------------
        # ADMIN ONLY
        # ----------------------------------------------------

        if request.user.role != "ADMIN":

            messages.error(
                request,
                "Only Admin can change a Won lead to Lost."
            )

            return redirect(
                "lead_detail",
                lead_id=lead.lead_id
            )

        # ----------------------------------------------------
        # LOST STAGE CONFIG
        # ----------------------------------------------------

        lost_stage_config = {
            "number": 7,
            "title": "Lost",
            "description": (
                "Record why this won opportunity was later lost."
            ),
            "next": None,
            "next_label": "",
        }

        # ----------------------------------------------------
        # POST - CONFIRM LOST
        # ----------------------------------------------------

        if request.method == "POST":

            lost_reason = request.POST.get(
                "lost_reason",
                ""
            ).strip()

            # ------------------------------------------------
            # VALIDATION
            # ------------------------------------------------

            if not lost_reason:

                messages.error(
                    request,
                    "Lost Reason is required."
                )

                return render(
                    request,
                    "leads/lead_stage_workflow.html",
                    {
                        "lead": lead,

                        "stage": "LOST",

                        "stage_config": lost_stage_config,

                        "stage_order": STAGE_ORDER,

                        "stage_config_all": STAGE_CONFIG,

                        "saved_data": {
                            "lost_reason": lost_reason
                        },

                        "previous_stage": "WON",

                        "won_to_lost": True,
                    }
                )

            # ------------------------------------------------
            # MAX LENGTH VALIDATION
            # ------------------------------------------------

            if len(lost_reason) > 100:

                messages.error(
                    request,
                    "Lost Reason cannot exceed 100 characters."
                )

                return render(
                    request,
                    "leads/lead_stage_workflow.html",
                    {
                        "lead": lead,

                        "stage": "LOST",

                        "stage_config": lost_stage_config,

                        "stage_order": STAGE_ORDER,

                        "stage_config_all": STAGE_CONFIG,

                        "saved_data": {
                            "lost_reason": lost_reason
                        },

                        "previous_stage": "WON",

                        "won_to_lost": True,
                    }
                )

            # ------------------------------------------------
            # SAVE WON -> LOST
            # ------------------------------------------------

            with transaction.atomic():

                old_status = lead.status

                # Change Lead status
                lead.status = Lead.Status.LOST

                # Save lost reason
                lead.lost_reason = lost_reason

                # ------------------------------------------------
                # Save Lost information in stage_data
                # ------------------------------------------------

                stage_data = lead.stage_data or {}

                stage_data["LOST"] = {
                    "lost_reason": lost_reason,

                    "changed_from": old_status,

                    "completed": True,

                    "completed_at": (
                        timezone.now().isoformat()
                    ),

                    "completed_by": (
                        request.user.id
                    ),
                }

                lead.stage_data = stage_data

                # Save Lead
                lead.save()
                customer = getattr(lead, "customer", None)

                if customer:
                   customer.status = Customer.Status.INACTIVE
                   customer.save(update_fields=["status", "updated_at"])

                # ------------------------------------------------
                # ACTIVITY HISTORY
                # ------------------------------------------------

                LeadActivity.objects.create(
                    lead=lead,

                    activity_type=(
                        LeadActivity.ActivityType.STATUS_CHANGE
                    ),

                    description=(
                        f"Lead changed from Won to Lost. "
                        f"Reason: {lost_reason}"
                    ),

                    created_by=request.user,
                )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            messages.success(
                request,
                f"{lead.lead_id} changed from Won to Lost."
            )

            return redirect(
                "lead_detail",
                lead_id=lead.lead_id
            )

        # ----------------------------------------------------
        # GET - SHOW WON -> LOST FORM
        # ----------------------------------------------------

        return render(
            request,
            "leads/lead_stage_workflow.html",
            {
                "lead": lead,

                "stage": "LOST",

                "stage_config": lost_stage_config,

                "stage_order": STAGE_ORDER,

                "stage_config_all": STAGE_CONFIG,

                "saved_data": {
                    "lost_reason": (
                        lead.lost_reason or ""
                    )
                },

                "previous_stage": "WON",

                "won_to_lost": True,
            }
        )

    # ========================================================
    # NORMAL STAGE ORDER
    # ========================================================

    if requested_stage in STAGE_ORDER:

        stage = requested_stage

    elif current_status == Lead.Status.NEW:

        stage = "CONTACTED"

    else:

        stage = current_status

    # ========================================================
# STAGE INDEX
# ========================================================

    if current_status == Lead.Status.LOST:

    # LOST is not part of the normal pipeline.
    # Use the stage from which the lead was changed to Lost.
     lost_data = (lead.stage_data or {}).get("LOST", {})

     changed_from = lost_data.get("changed_from")

     if changed_from in STAGE_ORDER:
        current_index = STAGE_ORDER.index(changed_from)
     else:
        # Fallback if old Lost data does not contain changed_from
         current_index = STAGE_ORDER.index("WON")

    else:

     current_index = STAGE_ORDER.index(
        current_status
    )


    requested_index = STAGE_ORDER.index(
    stage
)

    # ========================================================
    # PREVIOUS STAGE
    # ========================================================

    stage_index = STAGE_ORDER.index(
        stage
    )

    if stage_index > 1:

        previous_stage = STAGE_ORDER[
            stage_index - 1
        ]

    elif stage_index == 1:

        # Contacted -> Lead Detail
        previous_stage = None

    else:

        previous_stage = None

    # ========================================================
    # FUTURE STAGE PROTECTION
    # ========================================================

    if requested_index > current_index + 1:

        messages.warning(
            request,
            "Please complete the previous stage first."
        )

        if current_status == Lead.Status.NEW:

            return redirect(
                "lead_stage_workflow",
                lead_id=lead.lead_id
            )

        return redirect(
            f"/leads/{lead.lead_id}/stage/"
            f"?stage={current_status}"
        )

    # ========================================================
    # STAGE CONFIG
    # ========================================================

    stage_config = STAGE_CONFIG[stage]

    # ========================================================
    # EXISTING STAGE DATA
    # ========================================================

    stage_data = lead.stage_data or {}

    saved_data = stage_data.get(
        stage,
        {}
    )

    # ========================================================
    # POST
    # ========================================================

    if request.method == "POST":

        # ----------------------------------------------------
        # BUTTON ACTION
        # ----------------------------------------------------

        action = request.POST.get(
            "action",
            "continue"
        )

        data = {}

        # ====================================================
        # CONTACTED
        # ====================================================

        if stage == "CONTACTED":

            contact_person = request.POST.get(
                "contact_person",
                ""
            ).strip()

            phone = request.POST.get(
                "phone",
                ""
            ).strip()

            # Required only for Save & Continue
            if action == "continue":

                if not contact_person:

                    messages.error(
                        request,
                        "Contact Person is required."
                    )

                    return render(
                        request,
                        "leads/lead_stage_workflow.html",
                        {
                            "lead": lead,
                            "stage": stage,
                            "stage_config": stage_config,
                            "stage_order": STAGE_ORDER,
                            "stage_config_all": STAGE_CONFIG,
                            "saved_data": request.POST,
                            "previous_stage": previous_stage,
                        }
                    )

                if not phone:

                    messages.error(
                        request,
                        "Phone Number is required."
                    )

                    return render(
                        request,
                        "leads/lead_stage_workflow.html",
                        {
                            "lead": lead,
                            "stage": stage,
                            "stage_config": stage_config,
                            "stage_order": STAGE_ORDER,
                            "stage_config_all": STAGE_CONFIG,
                            "saved_data": request.POST,
                            "previous_stage": previous_stage,
                        }
                    )

            data = {
                "contact_person": contact_person,

                "company_name": request.POST.get(
                    "company_name",
                    ""
                ).strip(),

                "phone": phone,

                "location": request.POST.get(
                    "location",
                    ""
                ).strip(),

                "email": request.POST.get(
                    "email",
                    ""
                ).strip(),

                "preferred_contact_method": (
                    request.POST.get(
                        "preferred_contact_method",
                        ""
                    ).strip()
                ),

                "remarks": request.POST.get(
                    "remarks",
                    ""
                ).strip(),
            }

            # ------------------------------------------------
            # UPDATE LEAD INFORMATION
            # ------------------------------------------------

            if contact_person:

                name_parts = contact_person.split(
                    " ",
                    1
                )

                lead.first_name = name_parts[0]

                if len(name_parts) > 1:

                    lead.last_name = name_parts[1]

                else:

                    lead.last_name = ""

            if phone:

                lead.phone = phone

            if data["email"]:

                lead.email = data["email"]

            if data["company_name"]:

                lead.company = data["company_name"]

            if data["location"]:

                lead.location = data["location"]

        # ====================================================
        # QUALIFIED
        # ====================================================

        elif stage == "QUALIFIED":

            requirement = request.POST.get(
                "customer_requirement",
                ""
            ).strip()

            if (
                action == "continue"
                and not requirement
            ):

                messages.error(
                    request,
                    "Customer Requirement is required."
                )

                return render(
                    request,
                    "leads/lead_stage_workflow.html",
                    {
                        "lead": lead,
                        "stage": stage,
                        "stage_config": stage_config,
                        "stage_order": STAGE_ORDER,
                        "stage_config_all": STAGE_CONFIG,
                        "saved_data": request.POST,
                        "previous_stage": previous_stage,
                    }
                )

            data = {
                "customer_requirement": requirement,

                "budget": request.POST.get(
                    "budget",
                    ""
                ).strip(),

                "purchase_timeline": request.POST.get(
                    "purchase_timeline",
                    ""
                ).strip(),

                "decision_maker": request.POST.get(
                    "decision_maker",
                    ""
                ).strip(),

                "qualification_notes": request.POST.get(
                    "qualification_notes",
                    ""
                ).strip(),
            }

        # ====================================================
        # PROPOSAL
        # ====================================================

        elif stage == "PROPOSAL":

            proposal_value = request.POST.get(
                "proposal_value",
                ""
            ).strip()

            proposal_date = request.POST.get(
                "proposal_date",
                ""
            ).strip()

            proposal_details = request.POST.get(
                "proposal_details",
                ""
            ).strip()

            if (
                action == "continue"
                and not proposal_value
            ):

                messages.error(
                    request,
                    "Proposal Value is required."
                )

                return render(
                    request,
                    "leads/lead_stage_workflow.html",
                    {
                        "lead": lead,
                        "stage": stage,
                        "stage_config": stage_config,
                        "stage_order": STAGE_ORDER,
                        "stage_config_all": STAGE_CONFIG,
                        "saved_data": request.POST,
                        "previous_stage": previous_stage,
                    }
                )

            data = {
                "proposal_value": proposal_value,

                "proposal_date": proposal_date,

                "proposal_details": proposal_details,
            }

            if proposal_value:

                try:

                    lead.lead_value = proposal_value

                except Exception:

                    pass

        # ====================================================
        # NEGOTIATION
        # ====================================================

        elif stage == "NEGOTIATION":

            negotiation_value = request.POST.get(
                "negotiation_value",
                ""
            ).strip()

            expected_closing_date = request.POST.get(
                "expected_closing_date",
                ""
            ).strip()

            negotiation_notes = request.POST.get(
                "negotiation_notes",
                ""
            ).strip()

            data = {
                "negotiation_value": (
                    negotiation_value
                ),

                "expected_closing_date": (
                    expected_closing_date
                ),

                "negotiation_notes": (
                    negotiation_notes
                ),
            }

            if negotiation_value:

                lead.lead_value = negotiation_value

        # ====================================================
        # WON
        # ====================================================

        elif stage == "WON":

            final_deal_value = request.POST.get(
                "final_deal_value",
                ""
            ).strip()

            closing_date = request.POST.get(
                "closing_date",
                ""
            ).strip()

            final_notes = request.POST.get(
                "final_notes",
                ""
            ).strip()

            if (
                action == "continue"
                and not final_deal_value
            ):

                messages.error(
                    request,
                    "Final Deal Value is required."
                )

                return render(
                    request,
                    "leads/lead_stage_workflow.html",
                    {
                        "lead": lead,
                        "stage": stage,
                        "stage_config": stage_config,
                        "stage_order": STAGE_ORDER,
                        "stage_config_all": STAGE_CONFIG,
                        "saved_data": request.POST,
                        "previous_stage": previous_stage,
                    }
                )

            data = {
                "final_deal_value": (
                    final_deal_value
                ),

                "closing_date": (
                    closing_date
                ),

                "final_notes": (
                    final_notes
                ),
            }

            if final_deal_value:

                lead.lead_value = final_deal_value

        # ====================================================
        # SAVE TO DATABASE
        # ====================================================

        with transaction.atomic():

            # ------------------------------------------------
            # NEXT STAGE
            # ------------------------------------------------

            next_stage = stage_config["next"]

            # ------------------------------------------------
            # IS STAGE COMPLETED?
            # ------------------------------------------------

            completed = (
                action == "continue"
            )

            # ------------------------------------------------
            # SAVE STAGE INFORMATION
            # ------------------------------------------------

            stage_data[stage] = {

                **data,

                "completed": completed,

                "completed_at": (
                    timezone.now().isoformat()
                    if completed
                    else None
                ),

                "completed_by": (
                    request.user.id
                    if completed
                    else None
                ),
            }

            lead.stage_data = stage_data

            # ------------------------------------------------
            # SAVE & EXIT
            # ------------------------------------------------

            if action == "exit":

                lead.status = stage

            # ------------------------------------------------
            # SAVE & CONTINUE
            # ------------------------------------------------

            else:

                if next_stage:

                    lead.status = next_stage

                else:

                    lead.status = Lead.Status.WON

            # ------------------------------------------------
            # SAVE LEAD
            # ------------------------------------------------

            lead.save()

            # ------------------------------------------------
            # ACTIVITY
            # ------------------------------------------------

            if action == "continue":

                LeadActivity.objects.create(

                    lead=lead,

                    activity_type=(
                        LeadActivity.ActivityType.STATUS_CHANGE
                    ),

                    description=(
                        f"Stage completed: "
                        f"{stage_config['title']}."
                    ),

                    created_by=request.user,
                )

            else:

                LeadActivity.objects.create(

                    lead=lead,

                    activity_type=(
                        LeadActivity.ActivityType.NOTE
                    ),

                    description=(
                        f"{stage_config['title']} "
                        f"information saved. "
                        f"Stage remains open."
                    ),

                    created_by=request.user,
                )

            # =================================================
            # WON
            # =================================================

            if (
                stage == "WON"
                and action == "continue"
            ):

                customer = getattr(
                    lead,
                    "customer",
                    None
                )

                # ------------------------------------------------
                # CREATE CUSTOMER
                # ------------------------------------------------

                if not customer:

                    customer = Customer.objects.create(

                        first_name=lead.first_name,

                        last_name=lead.last_name,

                        phone=lead.phone,

                        whatsapp_number=lead.whatsapp_number,

                        email=lead.email,

                        company=lead.company,

                        source=lead.get_source_display(),

                        assigned_to=lead.assigned_to,

                        lead=lead,
                    )

                # ------------------------------------------------
                # CREATE DEAL
                # ------------------------------------------------

                if not customer.deals.exists():

                    Deal.objects.create(

                        customer=customer,

                        title=(
                            f"Deal for "
                            f"{customer.first_name} "
                            f"{customer.last_name}"
                        ).strip(),

                        deal_value=lead.lead_value,

                        status=Deal.Status.WON,

                        assigned_to=lead.assigned_to,

                        notes=data.get(
                            "final_notes",
                            ""
                        ),
                    )

                # ------------------------------------------------
                # CONVERSION ACTIVITY
                # ------------------------------------------------

                LeadActivity.objects.create(

                    lead=lead,

                    activity_type=(
                        LeadActivity.ActivityType.NOTE
                    ),

                    description=(
                        "Lead converted successfully "
                        "to Customer and Deal."
                    ),

                    created_by=request.user,
                )

    # ========================================================
    # SAVE & EXIT
    # ========================================================

        if action == "exit":

            messages.success(
                request,
                f"{stage_config['title']} "
                f"information saved successfully."
            )

            return redirect(
                "lead_list"
            )

        # ====================================================
        # SAVE & CONTINUE
        # ====================================================

        if next_stage:

            messages.success(
                request,
                f"{stage_config['title']} "
                f"completed successfully."
            )

            return redirect(
                f"/leads/{lead.lead_id}/stage/"
                f"?stage={next_stage}"
            )

        # ====================================================
        # WON COMPLETE
        # ====================================================

        messages.success(
            request,
            f"{lead.lead_id} "
            f"has been successfully converted to Won."
        )

        return redirect(
            "lead_detail",
            lead_id=lead.lead_id
        )

    # ========================================================
    # GET
    # ========================================================

    return render(
        request,
        "leads/lead_stage_workflow.html",
        {
            "lead": lead,

            "stage": stage,

            "stage_config": stage_config,

            "stage_order": STAGE_ORDER,

            "stage_config_all": STAGE_CONFIG,

            "saved_data": saved_data,

            "previous_stage": previous_stage,

        }
    )

def global_search(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({
            "results": []
        })

    # Search matching leads
    leads = Lead.objects.filter(
        Q(first_name__icontains=query)
        | Q(last_name__icontains=query)
        | Q(company__icontains=query)
        | Q(email__icontains=query)
        | Q(phone__icontains=query)
        | Q(whatsapp_number__icontains=query)
        | Q(lead_id__icontains=query)
    )

    # Sales Employee can search ONLY their assigned leads
    if request.user.role == User.Role.SALES:
        leads = leads.filter(
            assigned_to=request.user
        )

    # Admin and Manager can search all leads
    leads = leads.order_by("-created_at")[:10]

    results = []

    for lead in leads:
        full_name = f"{lead.first_name} {lead.last_name}".strip()

        results.append({
            "lead_id": lead.lead_id,
            "name": full_name,
            "company": lead.company or "",
            "url": f"/leads/{lead.lead_id}/",
        })

    return JsonResponse({
        "results": results
    })

@login_required
def whatsapp_conversation(request, lead_id):
    # Admin and Manager can access all leads.
    # Other users can access only their assigned leads.
    if request.user.role in ["ADMIN", "MANAGER"]:
        lead_queryset = Lead.objects.all()
    else:
        lead_queryset = Lead.objects.filter(assigned_to=request.user)

    lead = get_object_or_404(lead_queryset, lead_id=lead_id)

    from .models import WhatsAppMessage, WhatsAppQuickReply

    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        if action == "record_message":
            message = request.POST.get("message", "").strip()
            direction = request.POST.get("direction", "").strip()

            allowed_directions = [
                WhatsAppMessage.Direction.INCOMING,
                WhatsAppMessage.Direction.OUTGOING,
            ]

            if not message:
                messages.error(request, "Please enter a message.")
            elif direction not in allowed_directions:
                messages.error(request, "Please select a valid message direction.")
            else:
                WhatsAppMessage.objects.create(
                    lead=lead,
                    direction=direction,
                    message=message,
                    created_by=request.user,
                )
                messages.success(request, "Message recorded successfully.")

        return redirect("whatsapp_conversation", lead_id=lead.lead_id)

    conversation = lead.whatsapp_messages.select_related(
        "created_by"
    ).all()

    if request.user.role in ["ADMIN", "MANAGER"]:
        quick_replies = WhatsAppQuickReply.objects.filter(
            is_active=True
        ).filter(
            models.Q(is_shared=True) | models.Q(created_by=request.user)
        )
    else:
        quick_replies = WhatsAppQuickReply.objects.filter(
            is_active=True
        ).filter(
            models.Q(is_shared=True) | models.Q(created_by=request.user)
        )

    return render(
        request,
        "leads/whatsapp_conversation.html",
        {
            "lead": lead,
            "conversation": conversation,
            "quick_replies": quick_replies,
        },
    )


@login_required
def whatsapp_quick_replies(request):
    from .models import WhatsAppQuickReply

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        message = request.POST.get("message", "").strip()
        is_shared = (
            request.user.role in ["ADMIN", "MANAGER"]
            and request.POST.get("is_shared") == "on"
        )

        if not title or not message:
            messages.error(request, "Title and message are required.")
        else:
            WhatsAppQuickReply.objects.create(
                title=title,
                message=message,
                created_by=request.user,
                is_shared=is_shared,
            )
            messages.success(request, "Quick reply created successfully.")

        return redirect("whatsapp_quick_replies")

    if request.user.role in ["ADMIN", "MANAGER"]:
        quick_replies = WhatsAppQuickReply.objects.filter(
            models.Q(is_shared=True) | models.Q(created_by=request.user)
        )
    else:
        quick_replies = WhatsAppQuickReply.objects.filter(
            models.Q(is_shared=True) | models.Q(created_by=request.user)
        )

    return render(
        request,
        "leads/whatsapp_quick_replies.html",
        {"quick_replies": quick_replies},
    )
