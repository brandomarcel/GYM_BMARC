"""Reception read models use real scope policy, receipts and attendance records."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from gym_management.api.memberships import record_attendance
from gym_management.api.operations import get_reception_panel, list_attendance
from gym_management.api.setup import get_setup_businesses, get_setup_checklist
from gym_management.tests import test_memberships


class TestOperations(FrappeTestCase):
	def setUp(self):
		self.base = test_memberships.TestMemberships()
		self.base.setUp()
		self.addCleanup(self.base.doCleanups)
		self.fixture = self.base.fixture
		self.business, self.branch = self.base.business, self.base.branch
		self.contract = self.base.contract(
			plan=self.base.plan(
				duration=3, duration_unit="Dias", payment_policy="Abonos", minimum_percentage=10
			)
		)

	def receipt(self, value=10):
		from facturada_lite.api.receipts import record_receipt

		return record_receipt(
			{
				"business": self.business,
				"source_doctype": "GYM Membership",
				"source_name": self.contract.name,
				"amount": value,
				"payment_method": "Transferencia",
				"reference": "TEST",
				"request_key": frappe.generate_hash(length=32),
			}
		)

	def history(self, **extra):
		return list_attendance(self.business, nowdate(), nowdate(), **extra)

	def attendance(self, **extra):
		return record_attendance(
			self.business, self.branch, self.base.member, frappe.generate_hash(length=32), **extra
		)

	def test_panel_counts_contracts_and_receipts_without_fiscal_permissions(self):
		self.receipt()
		self.attendance()
		self.fixture.act_as()
		data = get_reception_panel(self.business, self.branch)
		self.assertEqual(data["cards"]["active_contracts"], 1)
		self.assertEqual(data["cards"]["expiring_contracts"], 1)
		self.assertEqual(data["cards"]["outstanding"], 20)
		self.assertEqual(data["cards"]["entries_today"], 1)
		self.assertEqual(data["lists"]["with_balance"][0]["name"], self.contract.name)
		self.assertEqual(data["currency"], "USD")

	def test_attendance_keeps_denials_and_date_boundaries(self):
		self.attendance()
		self.receipt()
		self.attendance()
		old = self.attendance()
		frappe.db.set_value(
			"GYM Attendance", old["name"], "recorded_at", add_days(nowdate(), -1) + " 23:59:59"
		)
		self.fixture.act_as()
		rows = self.history()
		self.assertEqual(rows["totals"], {"records": 2, "allowed": 1, "denied": 1})
		self.assertEqual(self.history(result="Denegado")["totals"]["records"], 1)
		self.assertEqual(self.history(result="Permitido")["totals"]["records"], 1)
		self.assertEqual(len(rows["data"]), 2)

	def test_business_and_explicit_foreign_branch_are_denied(self):
		self.fixture.act_as()
		for business, branch in (
			(self.fixture.businesses[1].name, self.fixture.branches[1].name),
			(self.business, self.fixture.other_branch.name),
			(self.business, self.fixture.branches[1].name),
		):
			with self.assertRaises(frappe.PermissionError):
				get_reception_panel(business, branch)
			with self.assertRaises(frappe.PermissionError):
				list_attendance(business, nowdate(), nowdate(), branch)

	def test_unfiltered_totals_and_names_do_not_leak_other_branches(self):
		self.attendance()
		other = self.base.contract(
			member=self.fixture.other_member.name, origin_branch=self.fixture.other_branch.name
		)
		record_attendance(
			self.business, self.fixture.other_branch.name, self.fixture.other_member.name, "other-branch"
		)
		# A visit is visible at its recorded branch; the foreign home profile is not.
		visit = record_attendance(self.business, self.branch, self.fixture.other_member.name, "visitor")
		self.fixture.act_as()
		panel = get_reception_panel(self.business)
		self.assertEqual(panel["cards"]["active_contracts"], 1)
		self.assertNotIn(other.name, [row.name for row in panel["lists"]["with_balance"]])
		rows = self.history()
		self.assertEqual(rows["totals"]["records"], 2)
		self.assertIsNone(next(row.member_name for row in rows["data"] if row.name == visit["name"]))

	def test_revoked_assignment_and_disabled_feature_take_effect(self):
		self.attendance()
		frappe.db.set_value(
			"GYM Branch User", {"business": self.business, "branch": self.branch}, "status", "Inactivo"
		)
		self.fixture.act_as()
		self.assertEqual(self.history()["totals"]["records"], 0)
		self.assertEqual(get_reception_panel(self.business)["cards"]["active_contracts"], 0)
		frappe.set_user("Administrator")
		frappe.db.set_value("FacturADA Business Subscription", {"business": self.business}, "enable_gym", 0)
		self.fixture.act_as()
		with self.assertRaises(frappe.ValidationError):
			get_reception_panel(self.business)
		with self.assertRaises(frappe.ValidationError):
			self.history()

	def test_invalid_filters_cannot_change_query_scope(self):
		for values in (
			{"from_date": "oops"},
			{"from_date": "2020-01-01"},
			{"from_date": add_days(nowdate(), 1)},
			{"result": "Permitido' OR 1=1"},
			{"page": 0},
			{"page_size": 100000},
		):
			with self.assertRaises(frappe.ValidationError):
				list_attendance(
					**{"business": self.business, "from_date": nowdate(), "to_date": nowdate(), **values}
				)
		for days in (0, -1, 91):
			with self.assertRaises(frappe.ValidationError):
				get_reception_panel(self.business, horizon_days=days)

	def test_pagination_has_stable_order_and_totals(self):
		for _index in range(27):
			self.attendance()
		self.fixture.act_as()
		first = self.history(page_size=25)
		second = self.history(page=2, page_size=25)
		self.assertEqual(first["pagination"]["total"], 27)
		self.assertTrue(first["pagination"]["has_next"])
		self.assertFalse(second["pagination"]["has_next"])
		self.assertEqual(len(first["data"]), 25)
		self.assertEqual(len(second["data"]), 2)
		self.assertFalse({r.name for r in first["data"]} & {r.name for r in second["data"]})

	def test_cancelled_receipts_and_draft_contracts_are_not_counted(self):
		from facturada_lite.api.receipts import cancel_receipt

		receipt = self.receipt()
		cancel_receipt(receipt["name"], "Prueba")
		self.base.contract(submit=False)
		panel = get_reception_panel(self.business)
		self.assertEqual(panel["cards"]["active_contracts"], 1)
		self.assertEqual(panel["cards"]["outstanding"], 30)

	def test_panel_without_lite_does_not_require_its_tables(self):
		apps = [app for app in frappe.get_installed_apps() if app != "facturada_lite"]
		with patch("gym_management.operations.frappe.get_installed_apps", return_value=apps):
			panel = get_reception_panel(self.business)
		self.assertFalse(panel["payments_available"])
		self.assertEqual(panel["cards"]["outstanding"], 30)

	def test_setup_checklist_is_read_only_and_for_technical_admin(self):
		before = frappe.db.count("GYM Branch", {"business": self.business})
		self.assertIn(self.business, [row.name for row in get_setup_businesses()])
		data = get_setup_checklist(self.business)
		self.assertTrue(next(row["ready"] for row in data["steps"] if row["key"] == "subscription"))
		self.assertEqual(frappe.db.count("GYM Branch", {"business": self.business}), before)
		frappe.db.delete("FacturADA Business Subscription", {"business": self.business})
		with patch("gym_management.api.setup.is_feature_enabled", return_value=True):
			data = get_setup_checklist(self.business)
		self.assertFalse(next(row["ready"] for row in data["steps"] if row["key"] == "subscription"))
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			get_setup_checklist(self.business)
		with self.assertRaises(frappe.PermissionError):
			get_setup_businesses()

	def test_panel_distinguishes_dates_and_ignores_cancelled_contracts(self):
		for code, start, cancel in (
			("EXPIRED", add_days(nowdate(), -10), False),
			("FUTURE", add_days(nowdate(), 10), False),
			("CANCELLED", nowdate(), True),
		):
			member = self.fixture.make_member(0, member_code=code)
			contract = self.base.contract(
				member=member.name, start_date=start, plan=self.base.plan(duration=3, duration_unit="Dias")
			)
			if cancel:
				contract.cancel()
		cards = get_reception_panel(self.business)["cards"]
		self.assertEqual(cards["active_contracts"], 1)
		self.assertEqual(cards["expiring_contracts"], 1)
		self.assertEqual(cards["expired_contracts"], 1)
		self.assertEqual(cards["contracts_with_balance"], 3)
		self.assertEqual(cards["outstanding"], 90)
