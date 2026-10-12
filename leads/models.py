from django.conf import settings
from django.db import models

from django.core.validators import RegexValidator

class Lead(models.Model):

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        QUALIFIED = "QUALIFIED", "Qualified"
        PROPOSAL = "PROPOSAL", "Proposal"
        NEGOTIATION = "NEGOTIATION", "Negotiation"
        WON = "WON", "Won"
        LOST = "LOST", "Lost"

    class Temperature(models.TextChoices):
        HOT = "HOT", "Hot"
        WARM = "WARM", "Warm"
        COLD = "COLD", "Cold"

    class Priority(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    class Source(models.TextChoices):
        WEBSITE = "WEBSITE", "Website"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        FACEBOOK = "FACEBOOK", "Facebook"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        GOOGLE_ADS = "GOOGLE_ADS", "Google Ads"
        REFERRAL = "REFERRAL", "Referral"
        PHONE = "PHONE", "Phone Call"
        WALK_IN = "WALK_IN", "Walk-in"
        EMAIL = "EMAIL", "Email"
        JUSTDIAL = "JUSTDIAL", "Justdial"
        OTHER = "OTHER", "Other"

    lead_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    first_name = models.CharField(
        max_length=100
    )

    last_name = models.CharField(
        max_length=100,
        blank=True
    )

    
    phone = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r"^[6-9]\d{9}$",
                message="Enter a valid 10-digit Indian mobile number."
            )
        ]
    )

    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[6-9]\d{9}$",
                message="Enter a valid 10-digit Indian mobile number."
            )
        ]
    )

    email = models.EmailField(
        blank=True
    )

    company = models.CharField(
        max_length=150,
        blank=True
    )

    location = models.CharField(
        max_length=150,
        blank=True
    )

    category = models.CharField(
        max_length=100,
        blank=True
    )

    total_employees = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    source = models.CharField(
        max_length=30,
        choices=Source.choices,
        default=Source.OTHER
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW
    )

    lost_reason = models.CharField(
        max_length=100,
        blank=True
    )

    temperature = models.CharField(
        max_length=10,
        choices=Temperature.choices,
        default=Temperature.WARM
    )

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )

    lead_score = models.PositiveIntegerField(
        default=0
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_leads"
    )

    lead_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    next_follow_up = models.DateTimeField(
        null=True,
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    stage_data = models.JSONField(
        default=dict,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def save(self, *args, **kwargs):
        from decimal import Decimal

        # Convert numeric form values to the correct types
        if self.lead_value is None or self.lead_value == "":
            self.lead_value = Decimal("0")
        else:
            self.lead_value = Decimal(str(self.lead_value))

        if self.total_employees is not None and self.total_employees != "":
            self.total_employees = int(self.total_employees)

        # Generate Lead ID
        if not self.lead_id:
            last_lead = Lead.objects.order_by("-id").first()

            if last_lead:
                next_number = last_lead.id + 1
            else:
                next_number = 1

            self.lead_id = f"LEAD-{next_number:05d}"

        # Automatically set High priority for Hot leads
        if self.temperature == self.Temperature.HOT:
            self.priority = self.Priority.HIGH

        # Calculate Lead Score
        score = 0

        # Temperature score
        if self.temperature == self.Temperature.HOT:
            score += 30
        elif self.temperature == self.Temperature.WARM:
            score += 20
        else:
            score += 10

        # Priority score
        if self.priority == self.Priority.HIGH:
            score += 25
        elif self.priority == self.Priority.MEDIUM:
            score += 15
        else:
            score += 5

        # Status score
        if self.status == self.Status.NEW:
            score += 5
        elif self.status == self.Status.CONTACTED:
            score += 10
        elif self.status == self.Status.QUALIFIED:
            score += 20
        elif self.status == self.Status.PROPOSAL:
            score += 25
        elif self.status == self.Status.NEGOTIATION:
            score += 30
        elif self.status == self.Status.WON:
            score += 40

        # Lead value score
        if self.lead_value >= Decimal("100000"):
            score += 20
        elif self.lead_value >= Decimal("50000"):
            score += 15
        elif self.lead_value > Decimal("0"):
            score += 10

        # Company size score
        if self.total_employees:
            if self.total_employees >= 1000:
                score += 15
            elif self.total_employees >= 500:
                score += 10
            elif self.total_employees >= 100:
                score += 5

        # Maximum score should never exceed 100
        self.lead_score = min(score, 100)

        super().save(*args, **kwargs)
       


class LeadDocument(models.Model):
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    file = models.FileField(
        upload_to="lead_documents/"
    )

    original_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    file_size = models.PositiveBigIntegerField(
        default=0
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_lead_documents"
    )

    def __str__(self):
        return f"{self.lead.lead_id} - {self.original_name}"

class LeadActivity(models.Model):

    class ActivityType(models.TextChoices):
        CALL = "CALL", "Call"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        EMAIL = "EMAIL", "Email"
        MEETING = "MEETING", "Meeting"
        NOTE = "NOTE", "Note"
        STATUS_CHANGE = "STATUS_CHANGE", "Status Change"
        FOLLOW_UP = "FOLLOW_UP", "Follow-up"
        TASK_COMPLETED = "TASK_COMPLETED", "Task Completed"

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="activities"
    )

    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices
    )

    description = models.TextField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_activities"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.lead.lead_id} - {self.activity_type}"


class LeadTask(models.Model):

    class Priority(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="tasks"
    )

    title = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks"
    )

    due_date = models.DateTimeField()

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING
    )

    

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    @property
    def is_overdue(self):
        from django.utils import timezone

        return (
            self.status == self.Status.PENDING
            and self.due_date < timezone.now()
        )

    def save(self, *args, **kwargs):
        from django.utils import timezone

        was_completed = False

        if self.pk:
            old_task = LeadTask.objects.get(pk=self.pk)
            was_completed = old_task.status == self.Status.COMPLETED

        if (
            self.status == self.Status.COMPLETED
            and self.completed_at is None
        ):
            self.completed_at = timezone.now()

        if self.status != self.Status.COMPLETED:
            self.completed_at = None

        super().save(*args, **kwargs)

        if (
            self.status == self.Status.COMPLETED
            and not was_completed
        ):
            LeadActivity.objects.create(
                lead=self.lead,
                activity_type=LeadActivity.ActivityType.TASK_COMPLETED,
                description=f"Task completed: {self.title}",
                created_by=self.assigned_to,
            )

    def __str__(self):
        return f"{self.title} - {self.lead.lead_id}"

class LeadAssignmentHistory(models.Model):
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="assignment_history"
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_assignment_history"
    )

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_assignments_made"
    )

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.lead.lead_id} assigned to {self.assigned_to}"

class Customer(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    customer_id = models.CharField(max_length=20, unique=True, editable=False)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)

    phone = models.CharField(max_length=20)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    company = models.CharField(max_length=150, blank=True)

    source = models.CharField(max_length=30, blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers"
    )

    lead = models.OneToOneField(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.customer_id:
            last_customer = Customer.objects.order_by("-id").first()

            if last_customer:
                next_number = last_customer.id + 1
            else:
                next_number = 1

            self.customer_id = f"CUST-{next_number:05d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_id} - {self.first_name} {self.last_name}".strip()

class Deal(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        WON = "WON", "Won"
        LOST = "LOST", "Lost"
        CANCELLED = "CANCELLED", "Cancelled"

    deal_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="deals"
    )

    title = models.CharField(
        max_length=200
    )

    deal_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    expected_close_date = models.DateField(
        null=True,
        blank=True
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals"
    )

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def save(self, *args, **kwargs):

        if not self.deal_id:

            last_deal = Deal.objects.order_by("-id").first()

            if last_deal:
                next_number = last_deal.id + 1
            else:
                next_number = 1

            self.deal_id = f"DEAL-{next_number:05d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.deal_id} - {self.title}"

class Notification(models.Model):

    class NotificationType(models.TextChoices):
        FOLLOW_UP = "FOLLOW_UP", "Follow-up Reminder"
        TASK = "TASK", "Task Reminder"
        OVERDUE = "OVERDUE", "Overdue"
        LEAD_ASSIGNED = "LEAD_ASSIGNED", "Lead Assigned"
        STATUS_CHANGE = "STATUS_CHANGE", "Status Change"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )

    task = models.ForeignKey(
        LeadTask,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )

    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )

    title = models.CharField(
        max_length=200
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.title}"

class TaskAssignmentHistory(models.Model):

    task = models.ForeignKey(
        LeadTask,
        on_delete=models.CASCADE,
        related_name="assignment_history"
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_assignment_history"
    )

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks_assigned_by"
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        if self.assigned_to:
            return (
                f"{self.task.title} → "
                f"{self.assigned_to.username}"
            )

        return f"{self.task.title} → Unassigned"

CURRENCY_CHOICES = [
    ("INR", "INR - Indian Rupee (₹)"),
    ("USD", "USD - US Dollar ($)"),
    ("EUR", "EUR - Euro (€)"),
    ("GBP", "GBP - British Pound (£)"),
    ("AED", "AED - UAE Dirham"),
    ("SGD", "SGD - Singapore Dollar (S$)"),
    ("AUD", "AUD - Australian Dollar (A$)"),
    ("CAD", "CAD - Canadian Dollar (C$)"),
    ("JPY", "JPY - Japanese Yen (¥)"),
]

TIMEZONE_CHOICES = [
    ("Asia/Kolkata", "India Standard Time"),
    ("Asia/Dubai", "Gulf Standard Time"),
    ("Asia/Singapore", "Singapore Time"),
    ("Asia/Tokyo", "Japan Standard Time"),
    ("Europe/London", "United Kingdom"),
    ("Europe/Paris", "Central European Time"),
    ("America/New_York", "Eastern Time"),
    ("America/Chicago", "Central Time"),
    ("America/Denver", "Mountain Time"),
    ("America/Los_Angeles", "Pacific Time"),
    ("Australia/Sydney", "Australian Eastern Time"),
]

class CompanySettings(models.Model):
    company_name = models.CharField(
        max_length=150,
        default="My Company"
    )

    company_email = models.EmailField(
        blank=True
    )

    company_phone = models.CharField(
        max_length=20,
        blank=True
    )

    company_address = models.TextField(
        blank=True
    )

    website = models.URLField(
        blank=True
    )

    company_logo = models.ImageField(
        upload_to="company/",
        blank=True,
        null=True
    )

    timezone = models.CharField(
        max_length=100,
        choices=TIMEZONE_CHOICES,
        default="Asia/Kolkata"
    )

    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="INR"
    )

    date_format = models.CharField(
        max_length=30,
        default="DD/MM/YYYY"
    )

    working_hours_start = models.TimeField(
        default="09:00"
    )

    working_hours_end = models.TimeField(
        default="18:00"
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.company_name
class SupportTicket(models.Model):

    class Category(models.TextChoices):
        LEAD = "LEAD", "Lead Management"
        TASK = "TASK", "Tasks & Follow-ups"
        USER = "USER", "Users & Permissions"
        REPORT = "REPORT", "Reports & Analytics"
        SETTINGS = "SETTINGS", "Settings"
        OTHER = "OTHER", "Other"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    ticket_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets"
    )

    subject = models.CharField(
        max_length=200
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices
    )

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )

    description = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["category"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["assigned_to"]),
        ]

    def save(self, *args, **kwargs):

        if not self.ticket_id:
            last_ticket = SupportTicket.objects.order_by("-id").first()

            if last_ticket:
                next_number = last_ticket.id + 1
            else:
                next_number = 1

            self.ticket_id = f"TICKET-{next_number:05d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_id} - {self.subject}"