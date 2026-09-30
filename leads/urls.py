from django.urls import path
from . import views

from .views import (
    create_lead,
    edit_lead,
    add_activity,
    lead_list,
    lead_detail,
    follow_up_list,
    complete_task,
    pipeline,
    my_work_today,
    lead_inbox,
    add_follow_up,
    deal_list,
    create_deal,
    deal_detail,
    edit_deal,
    change_deal_status,
    upload_lead_document,
    delete_lead_document,
    assign_lead,
)

urlpatterns = [
    path("", lead_list, name="lead_list"),
    path("new/", create_lead, name="create_lead"),
    path("follow-ups/", follow_up_list, name="follow_up_list"),
    path("tasks/<int:task_id>/complete/", complete_task, name="complete_task"),
    path("pipeline/", pipeline, name="pipeline"),
    path("my-work-today/", my_work_today, name="my_work_today"),
    path("inbox/", lead_inbox, name="lead_inbox"),

    path("deals/", deal_list, name="deal_list"),
    path("deals/new/", create_deal, name="create_deal"),
    path("deals/<str:deal_id>/edit/", edit_deal, name="edit_deal"),
    path(
    "deals/<str:deal_id>/change-status/",
    change_deal_status,
    name="change_deal_status"
),
    path("deals/<str:deal_id>/", deal_detail, name="deal_detail"),
    path("<str:lead_id>/follow-up/add/", add_follow_up, name="add_follow_up"),
    path("<str:lead_id>/document/upload/", upload_lead_document, name="upload_lead_document"),
    path("document/<int:document_id>/delete/",delete_lead_document,name="delete_lead_document",),
    path("<str:lead_id>/edit/", edit_lead, name="edit_lead"),
    path("<str:lead_id>/activity/add/", add_activity, name="add_activity"),
    path("<str:lead_id>/assign/", assign_lead, name="assign_lead"),
    path("tasks/create/", views.create_task, name="create_task"),
    path("tasks/", views.admin_task_list, name="admin_task_list"),
    path("settings/", views.admin_settings, name="admin_settings"),
    path("reports/", views.admin_reports, name="admin_reports"),
    path("tasks/<int:task_id>/complete/", views.complete_task, name="complete_task"),
    path("tasks/<int:task_id>/cancel/", views.cancel_task, name="cancel_task"),
    path("tasks/<int:task_id>/reassign/", views.reassign_task, name="reassign_task"),
    path("tasks/<int:task_id>/", views.task_detail, name="task_detail"),
    path("notifications/",views.notification_list,name="notification_list"),
    path("notifications/<int:notification_id>/read/",views.mark_notification_read,name="mark_notification_read"),
    path("help/", views.help_page, name="help"),
    path("report-issue/", views.report_issue, name="report_issue"),
    path("<str:lead_id>/", lead_detail, name="lead_detail"),
    path("leads/<str:lead_id>/move-next/",views.move_to_next_stage,name="move_to_next_stage"),
    path(
    "<str:lead_id>/stage/<str:stage>/",
    views.lead_stage,
    name="lead_stage",
    
),
    path(
    "<str:lead_id>/stage/",
    views.lead_stage_workflow,
    name="lead_stage_workflow",
),
path(
    "<str:lead_id>/notes/update/",
    views.update_lead_notes,
    name="update_lead_notes",
),
   
   
]