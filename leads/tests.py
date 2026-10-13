
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Lead, LeadTask, LeadActivity


User = get_user_model()


class LeadModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testemployee",
            email="testemployee@example.com",
            password="TestPassword123",
            role="SALES",
        )

    def create_lead(self, **kwargs):
        data = {
            "first_name": "Rahul",
            "last_name": "Sharma",
            "phone": "9876543210",
            "assigned_to": self.user,
        }
        data.update(kwargs)
        return Lead.objects.create(**data)

    def test_lead_id_is_generated_automatically(self):
        lead = self.create_lead()

        self.assertTrue(lead.lead_id.startswith("LEAD-"))
        self.assertEqual(len(lead.lead_id), 10)

    def test_new_lead_has_default_status(self):
        lead = self.create_lead()

        self.assertEqual(lead.status, Lead.Status.NEW)

    def test_hot_lead_gets_high_priority(self):
        lead = self.create_lead(
            temperature=Lead.Temperature.HOT
        )

        self.assertEqual(lead.priority, Lead.Priority.HIGH)


class LeadTaskModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="taskemployee",
            email="taskemployee@example.com",
            password="TestPassword123",
            role="SALES",
        )

        self.lead = Lead.objects.create(
            first_name="Priya",
            last_name="Patil",
            phone="9876543211",
            assigned_to=self.user,
        )

    def create_task(self, **kwargs):
        data = {
            "lead": self.lead,
            "title": "Call the customer",
            "assigned_to": self.user,
            "due_date": timezone.now() + timedelta(days=1),
        }
        data.update(kwargs)
        return LeadTask.objects.create(**data)

    def test_pending_task_is_not_overdue_before_due_date(self):
        task = self.create_task()

        self.assertFalse(task.is_overdue)

    def test_pending_task_is_overdue_after_due_date(self):
        task = self.create_task(
            due_date=timezone.now() - timedelta(days=1)
        )

        self.assertTrue(task.is_overdue)

    def test_completed_task_gets_completion_timestamp(self):
        task = self.create_task(
            status=LeadTask.Status.COMPLETED
        )

        self.assertIsNotNone(task.completed_at)

    def test_completing_task_creates_activity(self):
        task = self.create_task()

        task.status = LeadTask.Status.COMPLETED
        task.save()

        activity = LeadActivity.objects.filter(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.TASK_COMPLETED,
            description=f"Task completed: {task.title}",
        )

        self.assertEqual(activity.count(), 1)


class LeadAccessPermissionTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="testadmin",
            email="testadmin@example.com",
            password="TestPassword123",
            role="ADMIN",
        )

        self.employee_one = User.objects.create_user(
            username="employeeone",
            email="employeeone@example.com",
            password="TestPassword123",
            role="SALES",
        )

        self.employee_two = User.objects.create_user(
            username="employeetwo",
            email="employeetwo@example.com",
            password="TestPassword123",
            role="SALES",
        )

        self.lead_one = Lead.objects.create(
            first_name="Rahul",
            last_name="Sharma",
            phone="9876543210",
            assigned_to=self.employee_one,
        )

        self.lead_two = Lead.objects.create(
            first_name="Priya",
            last_name="Patil",
            phone="9876543211",
            assigned_to=self.employee_two,
        )

    def test_admin_can_see_all_leads(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("lead_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lead_one.lead_id)
        self.assertContains(response, self.lead_two.lead_id)

    def test_employee_sees_only_assigned_leads(self):
        self.client.force_login(self.employee_one)

        response = self.client.get(reverse("lead_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lead_one.lead_id)
        self.assertNotContains(response, self.lead_two.lead_id)

    def test_employee_cannot_open_another_employees_lead(self):
        self.client.force_login(self.employee_one)

        response = self.client.get(
            reverse(
                "lead_detail",
                kwargs={"lead_id": self.lead_two.lead_id},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_employee_can_open_own_assigned_lead(self):
        self.client.force_login(self.employee_one)

        response = self.client.get(
            reverse(
                "lead_detail",
                kwargs={"lead_id": self.lead_one.lead_id},
            )
        )

        self.assertEqual(response.status_code, 200)


class TaskAccessPermissionTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.admin = User.objects.create_user(
            username="taskadmin",
            email="taskadmin@example.com",
            password="TestPassword123",
            role="ADMIN",
        )

        self.employee_one = User.objects.create_user(
            username="taskemployeeone",
            email="taskemployeeone@example.com",
            password="TestPassword123",
            role="SALES",
        )

        self.employee_two = User.objects.create_user(
            username="taskemployeetwo",
            email="taskemployeetwo@example.com",
            password="TestPassword123",
            role="SALES",
        )

        self.lead = Lead.objects.create(
            first_name="Test",
            last_name="Customer",
            phone="9876543212",
            assigned_to=self.employee_one,
        )

        self.own_task = LeadTask.objects.create(
            title="Call my customer",
            lead=self.lead,
            assigned_to=self.employee_one,
            due_date=timezone.now() + timedelta(days=1),
        )

        self.other_task = LeadTask.objects.create(
            title="Call another customer",
            lead=self.lead,
            assigned_to=self.employee_two,
            due_date=timezone.now() + timedelta(days=1),
        )

    def test_employee_can_view_own_task(self):
        self.client.force_login(self.employee_one)

        response = self.client.get(
            reverse("task_detail", kwargs={"task_id": self.own_task.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_view_another_employees_task(self):
        self.client.force_login(self.employee_one)

        response = self.client.get(
            reverse("task_detail", kwargs={"task_id": self.other_task.id})
        )

        # Current view redirects unauthorized employees to the dashboard.
        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

    def test_admin_can_view_employee_task(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("task_detail", kwargs={"task_id": self.other_task.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_complete_another_employees_task(self):
        self.client.force_login(self.employee_one)

        response = self.client.post(
            reverse("complete_task", kwargs={"task_id": self.other_task.id})
        )

        self.other_task.refresh_from_db()

        self.assertEqual(self.other_task.status, LeadTask.Status.PENDING)
        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

    def test_employee_cannot_cancel_another_employees_task(self):
        self.client.force_login(self.employee_one)

        response = self.client.post(
            reverse("cancel_task", kwargs={"task_id": self.other_task.id})
        )

        self.other_task.refresh_from_db()

        self.assertEqual(self.other_task.status, LeadTask.Status.PENDING)
        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

    def test_employee_cannot_reassign_task(self):
        self.client.force_login(self.employee_one)

        response = self.client.get(
            reverse("reassign_task", kwargs={"task_id": self.own_task.id})
        )

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

    def test_admin_can_reassign_task(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("reassign_task", kwargs={"task_id": self.own_task.id})
        )

        self.assertEqual(response.status_code, 200)

class LeadCreationTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="creationadmin",
            email="creationadmin@example.com",
            password="TestPassword123",
            role="ADMIN",
        )

        self.employee = User.objects.create_user(
            username="creationemployee",
            email="creationemployee@example.com",
            password="TestPassword123",
            role="SALES",
        )

        self.valid_data = {
            "first_name": "Amit",
            "last_name": "Patel",
            "phone": "9876543212",
            "whatsapp_number": "9876543213",
            "email": "amit@example.com",
            "company": "Example Company",
            "location": "Mumbai",
            "category": "IT",
            "source": "WEBSITE",
            "temperature": "WARM",
            "priority": "MEDIUM",
        }

    def test_admin_can_open_create_lead_form(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("create_lead"))

        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_create_lead(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("create_lead"),
            self.valid_data,
        )

        self.assertRedirects(
            response,
            reverse("lead_list"),
            fetch_redirect_response=False,
        )
        self.assertFalse(
            Lead.objects.filter(phone=self.valid_data["phone"]).exists()
        )

    def test_invalid_phone_does_not_create_lead(self):
        self.client.force_login(self.admin)

        data = self.valid_data.copy()
        data["phone"] = "12345"

        response = self.client.post(reverse("create_lead"), data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Lead.objects.filter(phone="12345").exists())

    def test_invalid_whatsapp_number_does_not_create_lead(self):
        self.client.force_login(self.admin)

        data = self.valid_data.copy()
        data["whatsapp_number"] = "12345"

        response = self.client.post(reverse("create_lead"), data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Lead.objects.filter(phone=self.valid_data["phone"]).exists()
        )

    def test_duplicate_phone_is_rejected(self):
        self.client.force_login(self.admin)

        Lead.objects.create(
            first_name="Existing",
            phone=self.valid_data["phone"],
            assigned_to=self.employee,
        )

        response = self.client.post(
            reverse("create_lead"),
            self.valid_data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Lead.objects.filter(phone=self.valid_data["phone"]).count(),
            1,
        )

    def test_duplicate_email_is_rejected(self):
        self.client.force_login(self.admin)

        Lead.objects.create(
            first_name="Existing",
            phone="9876543214",
            email=self.valid_data["email"],
            assigned_to=self.employee,
        )

        response = self.client.post(
            reverse("create_lead"),
            self.valid_data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Lead.objects.filter(phone=self.valid_data["phone"]).exists()
        )

    def test_admin_can_create_lead(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("create_lead"),
            self.valid_data,
        )

        self.assertEqual(Lead.objects.filter(
            phone=self.valid_data["phone"]
        ).count(), 1)

        lead = Lead.objects.get(phone=self.valid_data["phone"])

        self.assertEqual(lead.first_name, "Amit")
        self.assertEqual(lead.assigned_to, self.admin)
        self.assertRedirects(
            response,
            reverse("lead_stage_workflow", kwargs={"lead_id": lead.lead_id}),
            fetch_redirect_response=False,
        )



class LeadEditingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="edit_admin",
            email="edit_admin@example.com",
            password="testpass123",
            role="ADMIN",
        )

        self.employee = User.objects.create_user(
            username="edit_employee",
            email="edit_employee@example.com",
            password="testpass123",
            role="SALES",
        )

        self.lead = Lead.objects.create(
            first_name="Amit",
            last_name="Patel",
            phone="9876543212",
            whatsapp_number="9876543213",
            email="amit@example.com",
            company="Example Company",
            assigned_to=self.employee,
        )

        self.edit_url = reverse(
            "edit_lead",
            kwargs={"lead_id": self.lead.lead_id},
        )

    def test_admin_can_open_edit_lead_form(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.edit_url)

        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_edit_lead(self):
        self.client.force_login(self.employee)

        response = self.client.get(self.edit_url)

        self.assertRedirects(
            response,
            reverse(
                "lead_detail",
                kwargs={"lead_id": self.lead.lead_id},
            ),
        )

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.first_name, "Amit")

    def test_invalid_phone_does_not_update_lead(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            self.edit_url,
            {
                "first_name": "Updated",
                "last_name": "Patel",
                "phone": "123",
                "whatsapp_number": "9876543213",
            },
        )

        self.assertRedirects(response, self.edit_url)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.phone, "9876543212")
        self.assertEqual(self.lead.first_name, "Amit")

    def test_invalid_whatsapp_does_not_update_lead(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            self.edit_url,
            {
                "first_name": "Updated",
                "last_name": "Patel",
                "phone": "9876543212",
                "whatsapp_number": "123",
            },
        )

        self.assertRedirects(response, self.edit_url)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.whatsapp_number, "9876543213")
        self.assertEqual(self.lead.first_name, "Amit")



class WonToLostTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="wonlost_admin",
            email="wonlost_admin@example.com",
            password="testpass123",
            role="ADMIN",
        )

        self.employee = User.objects.create_user(
            username="wonlost_employee",
            email="wonlost_employee@example.com",
            password="testpass123",
            role="SALES",
        )

        self.lead = Lead.objects.create(
            first_name="Test",
            last_name="Customer",
            phone="9876543210",
            status=Lead.Status.WON,
            assigned_to=self.employee,
        )

    def test_admin_can_open_won_to_lost_form(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "lead_stage_workflow",
                kwargs={"lead_id": self.lead.lead_id},
            ),
            {"stage": "LOST"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "leads/lead_stage_workflow.html",
        )
        self.assertTrue(response.context["won_to_lost"])

    def test_admin_can_change_won_lead_to_lost(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "lead_stage_workflow",
                kwargs={"lead_id": self.lead.lead_id},
            ) + "?stage=LOST",
            {
                "lost_reason": "Customer cancelled the deal",
            },
        )

        self.lead.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.lead.status, Lead.Status.LOST)
        self.assertEqual(
            self.lead.lost_reason,
            "Customer cancelled the deal",
        )

        self.assertTrue(
            LeadActivity.objects.filter(
                lead=self.lead,
                activity_type=LeadActivity.ActivityType.STATUS_CHANGE,
                description__contains="Lead changed from Won to Lost",
                created_by=self.admin,
            ).exists()
        )

    def test_admin_cannot_change_won_to_lost_without_reason(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "lead_stage_workflow",
                kwargs={"lead_id": self.lead.lead_id},
            ) + "?stage=LOST",
            {
                "lost_reason": "",
            },
        )

        self.lead.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.lead.status, Lead.Status.WON)
        self.assertEqual(self.lead.lost_reason, "")

    def test_employee_cannot_change_won_to_lost(self):
        self.client.force_login(self.employee)
        self.client.post(
            reverse(
                "lead_stage_workflow",
                kwargs={"lead_id": self.lead.lead_id},
            ) + "?stage=LOST",
            {
                "lost_reason": "Customer cancelled the deal",
            },
        )

        self.lead.refresh_from_db()

        self.assertEqual(self.lead.status, Lead.Status.WON)
