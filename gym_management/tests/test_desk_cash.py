import frappe
from frappe.tests.utils import FrappeTestCase

from gym_management.api.cash import close_cash, get_cash_context, get_cash_summary, open_cash
from gym_management.tests import test_membership_payments


class TestDeskCash(FrappeTestCase):
	def setUp(self):
		self.payments = test_membership_payments.TestMembershipPayments()
		self.payments.setUp()
		self.addCleanup(self.payments.doCleanups)
		frappe.set_user("Administrator")
		sub = frappe.get_doc("FacturADA Business Subscription", {"business": self.payments.base.business})
		sub.enable_pos = 1
		sub.enable_billing = 1
		sub.save()
		establishment = frappe.get_doc(
			{
				"doctype": "FacturADA Establishment",
				"business": self.payments.base.business,
				"establishment_code": "001",
				"establishment_name": "Sede de prueba",
			}
		).insert()
		point = frappe.get_doc(
			{
				"doctype": "FacturADA Emission Point",
				"business": self.payments.base.business,
				"establishment": establishment.name,
				"emission_point_code": "001",
				"emission_point_name": "Caja de prueba",
			}
		).insert()
		assignment = frappe.db.get_value(
			"FacturADA Business User",
			{"business": self.payments.base.business, "user": self.payments.fixture.users[0].name},
			"name",
		)
		terminal = frappe.get_doc(
			{
				"doctype": "FacturADA POS Terminal",
				"business": self.payments.base.business,
				"establishment": establishment.name,
				"emission_point": point.name,
				"terminal_name": "Caja GYM",
				"users": [{"business_user": assignment}],
			}
		).insert()
		branch = frappe.get_doc("GYM Branch", self.payments.base.branch)
		branch.establishment = establishment.name
		branch.save()
		self.terminal = terminal.name
		self.business = self.payments.base.business
		self.branch = self.payments.base.branch
		self.user = self.payments.fixture.users[0].name

	def open(self, **values):
		return open_cash(
			self.business, self.branch, self.terminal, user=self.user, **{"opening_amount": 10, **values}
		)

	def test_open_pay_close_uses_shared_engine_and_does_not_duplicate(self):
		opening = self.open()
		with self.assertRaises(frappe.ValidationError):
			self.open()
		self.payments.fixture.act_as()
		context = get_cash_context(self.business, self.branch)
		self.assertEqual(context["opening"].name, opening["name"])
		self.assertFalse(context["can_manage"])
		self.assertEqual([row["name"] for row in context["users"]], [self.user])
		self.payments.pay(20, "desk-cash", payment_method="Efectivo", cash_opening=opening["name"])
		frappe.set_user("Administrator")
		summary = get_cash_summary(self.business, self.branch, opening["name"], user=self.user)
		self.assertEqual(summary["cash_system"], 30)
		closing = close_cash(self.business, self.branch, opening["name"], 29, user=self.user)
		self.assertEqual(closing["cash_system"], 30)
		self.assertEqual(closing["difference"], -1)
		self.assertEqual(
			frappe.db.get_value("FacturADA Restaurant Cash Opening", opening["name"], "status"), "Cerrada"
		)
		with self.assertRaises(frappe.ValidationError):
			close_cash(self.business, self.branch, opening["name"], 29, user=self.user)
		self.assertEqual(
			frappe.db.count("FacturADA Restaurant Cash Closing", {"cash_opening": opening["name"]}), 1
		)

	def test_reception_cannot_open_close_or_inspect_other_cashier(self):
		opening = self.open()
		self.payments.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			self.open()
		with self.assertRaises(frappe.PermissionError):
			close_cash(self.business, self.branch, opening["name"], 10)
		with self.assertRaises(frappe.PermissionError):
			get_cash_summary(self.business, self.branch, opening["name"])
		with self.assertRaises(frappe.PermissionError):
			get_cash_context(self.business, self.branch, user="Administrator")

	def test_business_branch_and_terminal_boundaries(self):
		opening = self.open()
		fixture = self.payments.fixture
		fixture.act_as(1)
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			get_cash_context(self.business, self.branch)
		fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			get_cash_context(self.business, fixture.other_branch.name)
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.PermissionError):
			open_cash(self.business, fixture.other_branch.name, self.terminal, 0, user="Administrator")
		with self.assertRaises(frappe.PermissionError):
			get_cash_summary(self.business, fixture.other_branch.name, opening["name"], user="Administrator")

	def test_invalid_amounts_disabled_user_and_missing_terminal(self):
		for value in (None, "", -1, "NaN", "Infinity"):
			with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
				self.open(opening_amount=value)
		with self.assertRaises(frappe.PermissionError):
			open_cash(self.business, self.branch, "", 0, user=self.user)
		frappe.db.set_value("User", self.user, "enabled", 0)
		with self.assertRaises(frappe.PermissionError):
			self.open()

	def test_disabled_pos_and_unconfigured_branch_are_explicit(self):
		self.assertEqual(
			get_cash_context(self.business, self.payments.fixture.other_branch.name)["terminals"], []
		)
		sub = frappe.get_doc("FacturADA Business Subscription", {"business": self.business})
		sub.enable_pos = 0
		sub.save()
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			get_cash_context(self.business, self.branch)

	def test_zero_fund_and_zero_count_are_explicit_valid_amounts(self):
		opening = self.open(opening_amount=0)
		closing = close_cash(self.business, self.branch, opening["name"], 0, user=self.user)
		self.assertEqual(closing["difference"], 0)
