from django.contrib import admin

from .models import (
    Lead,
    LeadActivity,
    LeadTask,
    LeadAssignmentHistory,
    Customer,
    Deal,
    Notification,
    WhatsAppMessage,
    WhatsAppQuickReply,
)



@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):

    list_display = (
        "lead_id",
        "first_name",
        "last_name",
        "phone",
        "source",
        "status",
        "temperature",
        "priority",
        "assigned_to",
        "lead_value",
        "next_follow_up",
    )

    list_filter = (
        "status",
        "temperature",
        "priority",
        "source",
    )

    search_fields = (
        "lead_id",
        "first_name",
        "last_name",
        "phone",
        "email",
        "company",
    )

    ordering = ("-created_at",)


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):

    list_display = (
        "lead",
        "activity_type",
        "description",
        "created_by",
        "created_at",
    )

    list_filter = (
        "activity_type",
        "created_at",
    )

    search_fields = (
        "lead__lead_id",
        "lead__first_name",
        "lead__last_name",
        "description",
    )

    ordering = ("-created_at",)


@admin.register(LeadTask)
class LeadTaskAdmin(admin.ModelAdmin):

    list_display = (
    "title",
    "lead",
    "assigned_to",
    "due_date",
    "priority",
    "status",
    "overdue_status",
    "completed_at",
    "created_at",
)

    list_filter = (
        "priority",
        "status",
        "due_date",
    )

    search_fields = (
        "title",
        "lead__lead_id",
        "lead__first_name",
        "lead__last_name",
        "assigned_to__username",
    )

    ordering = ("due_date",)

    @admin.display(description="Task Status")
    def overdue_status(self, obj):
        return "OVERDUE" if obj.is_overdue else "OK"

@admin.register(LeadAssignmentHistory)
class LeadAssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "lead",
        "assigned_to",
        "assigned_by",
        "assigned_at",
    )

    list_filter = (
        "assigned_at",
    )

    search_fields = (
        "lead__lead_id",
        "lead__first_name",
        "lead__last_name",
        "assigned_to__username",
        "assigned_by__username",
    )

    ordering = ("-assigned_at",)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "customer_id",
        "first_name",
        "last_name",
        "phone",
        "email",
        "company",
        "assigned_to",
        "created_at",
    )

    list_filter = ("assigned_to", "created_at")

    search_fields = (
        "customer_id",
        "first_name",
        "last_name",
        "phone",
        "email",
        "company",
    )

    ordering = ("-created_at",)

@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):

    list_display = (
        "deal_id",
        "title",
        "customer",
        "deal_value",
        "status",

        "expected_close_date",
        "assigned_to",
        "created_at",
    )

    list_filter = (
        "status",
        "assigned_to",
        "expected_close_date",
    )

    search_fields = (
        "deal_id",
        "title",
        "customer__customer_id",
        "customer__first_name",
        "customer__last_name",
        "customer__phone",
        "assigned_to__username",
    )

    ordering = ("-created_at",)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "notification_type",
        "title",
        "lead",
        "is_read",
        "created_at",
        "read_at",
    )

    list_filter = (
        "notification_type",
        "is_read",
        "created_at",
    )

    search_fields = (
        "user__username",
        "title",
        "message",
        "lead__lead_id",
    )

    ordering = ("-created_at",)

@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = (
        "lead",
        "direction",
        "message_time",
        "created_by",
        "created_at",
    )
    list_filter = ("direction", "message_time")
    search_fields = (
        "lead__lead_id",
        "lead__first_name",
        "lead__last_name",
        "message",
    )
    ordering = ("-message_time",)


@admin.register(WhatsAppQuickReply)
class WhatsAppQuickReplyAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "created_by",
        "is_shared",
        "is_active",
        "created_at",
    )
    list_filter = ("is_shared", "is_active")
    search_fields = ("title", "message")
    ordering = ("title",)
