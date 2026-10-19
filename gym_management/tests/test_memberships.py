import uuid

import frappe
from frappe.client import get, get_list
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from gym_management.api.memberships import approve_credit, check_access, create_membership, record_attendance
from gym_management.membership_rules import end_date
from gym_management.tests import test_business_isolation


class TestMemberships(FrappeTestCase):
	def setUp(self):
		self.fixture = test_business_isolation.TestBusinessIsolation()
		self.fixture.setUp()
		self.addCleanup(self.fixture.doCleanups)
		self.business = self.fixture.businesses[0].name
		self.branch = self.fixture.branches[0].name
		self.member = self.fixture.members[0].name

	def plan(self, **values):
		return frappe.get_doc(
			{
				"doctype": "GYM Membership Plan",
				"business": self.business,
				"plan_code": uuid.uuid4().hex[:10],
				"plan_name": "Plan de prueba",
				"duration": 1,
				"duration_unit": "Meses",
				"price": 30,
				"currency": "USD",
				**values,
			}
		).insert()

	def contract(self, plan=None, submit=True, **values):
		doc = frappe.get_doc(
			{
				"doctype": "GYM Membership",
				"business": self.business,
				"origin_branch": self.branch,
				"member": self.member,
				"plan": (plan or self.plan()).name,
				"start_date": nowdate(),
				**values,
			}
		).insert()
		return doc.submit() if submit else doc

	def test_calendar_boundaries(self):
		self.assertEqual(end_date("2028-02-01", 1, "Meses"), getdate("2028-02-29"))
		self.assertEqual(end_date("2027-02-01", 1, "Meses"), getdate("2027-02-28"))
		self.assertEqual(end_date("2026-01-31", 1, "Meses"), getdate("2026-02-27"))
		self.assertEqual(end_date("2026-10-17", 1, "Dias"), getdate("2026-10-17"))

	def test_contract_copies_server_policy_and_preserves_history(self):
		plan = self.plan()
		contract = self.contract(plan, price=1, total=1, end_date="2099-01-01")
		self.assertEqual(contract.total, 30)
		self.assertNotEqual(getdate(contract.end_date), getdate("2099-01-01"))
		plan.price = 99
		plan.save()
		contract.reload()
		self.assertEqual(contract.price, 30)
		contract.price = 1
		with self.assertRaises((frappe.ValidationError, frappe.PermissionError)):
			contract.save()

	def test_overlapping_contracts_are_rejected(self):
		plan = self.plan()
		self.contract(plan)
		with self.assertRaises(frappe.ValidationError):
			self.contract(plan)

	def test_continuous_renewal_and_return_start(self):
		plan = self.plan(renewal_mode="Continua")
		old = self.contract(plan)
		renewed = self.contract(plan, previous_membership=old.name)
		self.assertEqual(getdate(renewed.start_date), getdate(add_days(old.end_date, 1)))
		plan.renewal_mode = "Desde regreso"
		plan.save()
		returned_date = add_days(renewed.end_date, 15)
		returned = self.contract(plan, previous_membership=renewed.name, start_date=returned_date)
		self.assertEqual(getdate(returned.start_date), getdate(returned_date))

	def test_free_and_unpaid_access_and_immutable_attendance(self):
		self.contract(self.plan(price=0))
		self.fixture.act_as()
		access = check_access(self.business, self.branch, self.member)
		self.assertEqual(access["result"], "Permitido")
		first = record_attendance(self.business, self.branch, self.member, "same-request")
		second = record_attendance(self.business, self.branch, self.member, "same-request")
		self.assertEqual(first["name"], second["name"])
		doc = frappe.get_doc("GYM Attendance", first["name"])
		doc.reason = "Alterado"
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_credit_needs_explicit_authorization(self):
		contract = self.contract(self.plan(payment_policy="Credito"))
		self.fixture.act_as()
		self.assertEqual(check_access(self.business, self.branch, self.member)["result"], "Denegado")
		with self.assertRaises(frappe.PermissionError):
			approve_credit(contract.name, "No autorizado")
		frappe.set_user("Administrator")
		approve_credit(contract.name, "Crédito aprobado para prueba")
		self.fixture.act_as()
		self.assertEqual(check_access(self.business, self.branch, self.member)["result"], "Permitido")

	def test_wrong_business_branch_and_member_are_rejected(self):
		with self.assertRaises(frappe.PermissionError):
			self.plan(access_mode="Varias sedes", branches=[{"branch": self.fixture.branches[1].name}])
		with self.assertRaises(frappe.PermissionError):
			self.contract(member=self.fixture.members[1].name)
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			check_access(
				self.fixture.businesses[1].name, self.fixture.branches[1].name, self.fixture.members[1].name
			)

	def test_catalog_and_contract_permissions(self):
		plan = self.plan()
		own = self.contract(plan)
		self.fixture.act_as()
		self.assertEqual(get("GYM Membership", own.name).name, own.name)
		self.assertEqual(len(get_list("GYM Membership", fields=["name"])), 1)
		plan.price = 1
		with self.assertRaises(frappe.PermissionError):
			plan.save()
		with self.assertRaises(frappe.PermissionError):
			own.cancel()

	def test_creation_retries_do_not_duplicate_or_change_request(self):
		plan = self.plan()
		payload = {
			"business": self.business,
			"member": self.member,
			"origin_branch": self.branch,
			"plan": plan.name,
			"start_date": nowdate(),
			"request_key": "create-contract",
		}
		self.fixture.act_as()
		first = create_membership(payload)
		second = create_membership(payload)
		self.assertEqual(first["name"], second["name"])
		with self.assertRaises(frappe.ValidationError):
			create_membership({**payload, "start_date": add_days(nowdate(), 1)})

	def test_multisite_access_does_not_expose_full_foreign_branch_member(self):
		contract = self.contract(self.plan(price=0, access_mode="Todas las sedes"))
		assignment = frappe.get_doc(
			"GYM Branch User", {"branch": self.branch, "user": self.fixture.users[0].name}
		)
		assignment.status = "Inactivo"
		assignment.save()
		frappe.get_doc(
			{
				"doctype": "GYM Branch User",
				"business": self.business,
				"branch": self.fixture.other_branch.name,
				"user": self.fixture.users[0].name,
			}
		).insert()
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			get("GYM Member", self.member)
		result = record_attendance(self.business, self.fixture.other_branch.name, self.member, "multisede")
		self.assertEqual(result["result"], "Permitido")
		self.assertEqual(result["membership"], contract.name)

	def test_unpaid_contract_fails_closed(self):
		self.contract()
		self.fixture.act_as()
		self.assertEqual(check_access(self.business, self.branch, self.member)["result"], "Denegado")
