from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import frappe
from facturada_lite.api.receipts import cancel_receipt, record_receipt
from frappe.client import get, get_list
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from gym_management.api.memberships import check_access, payment_summary
from gym_management.tests import test_memberships


class TestMembershipPayments(FrappeTestCase):
	def setUp(self):
		self.base = test_memberships.TestMemberships()
		self.base.setUp()
		self.addCleanup(self.base.doCleanups)
		self.fixture = self.base.fixture
		self.contract = self.base.contract(self.base.plan(payment_policy="Abonos", minimum_percentage=50))
		self.fixture.act_as()

	def pay(self, value, key="payment", **fields):
		return record_receipt(
			{
				"business": self.base.business,
				"source_doctype": "GYM Membership",
				"source_name": self.contract.name,
				"payment_method": "Transferencia",
				"reference": "TEST-ONLY",
				"request_key": key,
				"amount": value,
				**fields,
			}
		)

	def access(self):
		return check_access(self.base.business, self.base.branch, self.base.member)

	def test_partial_payments_control_access_without_invoice(self):
		before = frappe.db.count("FacturADA Lite Invoice")
		self.pay(10, "first")
		self.assertEqual(self.access()["result"], "Denegado")
		self.pay(5, "second")
		self.assertEqual(self.access()["result"], "Permitido")
		self.assertEqual(payment_summary(self.contract)["outstanding"], 15)
		self.pay(15, "third")
		self.assertEqual(payment_summary(self.contract)["outstanding"], 0)
		self.assertEqual(frappe.db.count("FacturADA Lite Invoice"), before)

	def test_receipt_retries_compare_payload_and_prevent_overpayment(self):
		first = self.pay(10)
		self.assertEqual(first["name"], self.pay(10)["name"])
		with self.assertRaises(frappe.ValidationError):
			self.pay(11)
		with self.assertRaises(frappe.ValidationError):
			self.pay(21, "overpayment")

	def test_cancel_is_manager_only_and_changes_access(self):
		receipt = self.pay(15)
		with self.assertRaises(frappe.PermissionError):
			cancel_receipt(receipt["name"], "No autorizado")
		frappe.set_user("Administrator")
		cancel_receipt(receipt["name"], "Corrección de prueba")
		self.fixture.act_as()
		self.assertEqual(self.access()["result"], "Denegado")
		self.assertEqual(payment_summary(self.contract)["paid"], 0)

	def test_paid_contract_cannot_be_cancelled_with_money_attached(self):
		self.pay(15)
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.ValidationError):
			self.contract.cancel()

	def test_foreign_business_cannot_read_receipts_or_pay_source(self):
		receipt = self.pay(15)
		self.fixture.act_as(1)
		self.assertEqual(get_list("FacturADA Payment Receipt", fields=["name"]), [])
		with self.assertRaises(frappe.PermissionError):
			get("FacturADA Payment Receipt", receipt["name"])
		with self.assertRaises(frappe.PermissionError):
			self.pay(1, "foreign")

	def test_invalid_amounts_and_cash_without_opening_are_rejected(self):
		for value in (0, -1, "NaN", "Infinity"):
			with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
				self.pay(value, str(value))
		with self.assertRaises(frappe.ValidationError):
			self.pay(1, "cash", payment_method="Efectivo")

	def test_confirmed_receipt_cannot_be_modified(self):
		receipt = self.pay(15)
		doc = frappe.get_doc("FacturADA Payment Receipt", receipt["name"])
		doc.amount = 30
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			doc.save()

	def test_report_requires_management_permission_and_limits_business(self):
		self.pay(15)
		from gym_management.gym_bmarc.report.gym_membership_overview.gym_membership_overview import execute

		with self.assertRaises(frappe.PermissionError):
			execute({"business": self.base.business})
		frappe.set_user("Administrator")
		_, rows = execute({"business": self.base.business})
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].paid, 15)
		self.assertEqual(rows[0].outstanding, 15)

	def test_subcent_threshold_still_requires_a_real_payment(self):
		frappe.set_user("Administrator")
		self.contract.cancel()
		self.contract = self.base.contract(
			self.base.plan(price=0.01, payment_policy="Abonos", minimum_percentage=1)
		)
		self.fixture.act_as()
		self.assertEqual(self.access()["result"], "Denegado")

	def test_cash_receipt_is_counted_once_and_closed_cash_cannot_reverse(self):
		if "facturada_restaurante" not in frappe.get_installed_apps():
			self.skipTest("El conector de caja requiere Restaurante instalado explícitamente.")
		frappe.set_user("Administrator")
		sub = frappe.get_doc("FacturADA Business Subscription", {"business": self.base.business})
		sub.enable_pos = 1
		sub.enable_billing = 1
		sub.save()
		establishment = frappe.get_doc(
			{
				"doctype": "FacturADA Establishment",
				"business": self.base.business,
				"establishment_code": "001",
				"establishment_name": "Sede de prueba",
			}
		).insert()
		point = frappe.get_doc(
			{
				"doctype": "FacturADA Emission Point",
				"business": self.base.business,
				"establishment": establishment.name,
				"emission_point_code": "001",
				"emission_point_name": "Caja de prueba",
			}
		).insert()
		assignment = frappe.db.get_value(
			"FacturADA Business User",
			{"business": self.base.business, "user": self.fixture.users[0].name},
			"name",
		)
		terminal = frappe.get_doc(
			{
				"doctype": "FacturADA POS Terminal",
				"business": self.base.business,
				"establishment": establishment.name,
				"emission_point": point.name,
				"terminal_name": "Caja GYM",
				"users": [{"business_user": assignment}],
			}
		).insert()
		branch = frappe.get_doc("GYM Branch", self.base.branch)
		branch.establishment = establishment.name
		branch.save()
		opening = frappe.get_doc(
			{
				"doctype": "FacturADA Restaurant Cash Opening",
				"business": self.base.business,
				"user": self.fixture.users[0].name,
				"pos_terminal": terminal.name,
				"opening_amount": 10,
				"opened_at": nowdate(),
			}
		).insert()
		self.fixture.act_as()
		receipt = self.pay(20, "cash-once", payment_method="Efectivo", cash_opening=opening.name)
		from facturada_restaurante.api.frontend import close_cash_register, get_cash_payment_totals

		for _ in range(2):
			totals = get_cash_payment_totals(opening)
			self.assertEqual(sum(row.amount for row in totals if row.payment_code == "01"), 20)
		frappe.set_user("Administrator")
		close_cash_register(
			{
				"business": self.base.business,
				"user": opening.user,
				"cash_opening": opening.name,
				"cash_counted": 30,
			}
		)
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			cancel_receipt(receipt["name"], "Caja ya cerrada")

	def test_grace_deadline_is_independent_of_partial_payment(self):
		self.pay(15)
		from gym_management.api.memberships import evaluate_access

		self.assertEqual(
			evaluate_access(
				self.base.business, self.base.branch, self.base.member, at_date=add_days(nowdate(), 1)
			)["reason"],
			"Deuda vencida",
		)

	def cleanup_committed_fixture(self):
		frappe.set_user("Administrator")
		businesses = [b.name for b in self.fixture.businesses]
		for doctype in (
			"FacturADA Payment Receipt",
			"GYM Attendance",
			"GYM Membership",
			"GYM Membership Plan",
			"GYM Member",
			"GYM Branch User",
			"GYM Branch",
			"FacturADA Business User",
			"FacturADA Business Subscription",
		):
			names = frappe.get_all(doctype, filters={"business": ["in", businesses]}, pluck="name")
			if names:
				frappe.db.delete("GYM Membership Branch", {"parent": ["in", names], "parenttype": doctype})
			frappe.db.delete(doctype, {"business": ["in", businesses]})
		frappe.db.delete("FacturADA Business", {"name": ["in", businesses]})
		for user in self.fixture.users:
			frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)
		frappe.db.commit()

	def concurrent_payments(self, values):
		site, sites_path = frappe.local.site, frappe.local.sites_path
		user = frappe.session.user
		business, name = self.base.business, self.contract.name
		barrier = Barrier(2)
		frappe.db.commit()  # Separate connections must see these synthetic fixtures.
		self.addCleanup(self.cleanup_committed_fixture)

		def pay_from_connection(value):
			frappe.init(site=site, sites_path=sites_path)
			frappe.connect()
			try:
				frappe.flags.in_test = True
				frappe.set_user(user)
				# Both transactions start with a consistent snapshot before either pays.
				frappe.db.get_value("GYM Membership", name, "name")
				barrier.wait(timeout=10)
				result = record_receipt(
					{
						"business": business,
						"source_doctype": "GYM Membership",
						"source_name": name,
						"amount": value[0],
						"request_key": value[1],
						"payment_method": "Transferencia",
						"reference": "CONCURRENCY-TEST",
					}
				)
				frappe.db.commit()
				return result
			except frappe.ValidationError:
				frappe.db.rollback()
				return "rejected"
			finally:
				frappe.destroy()

		with ThreadPoolExecutor(max_workers=2) as executor:
			return list(executor.map(pay_from_connection, values))

	def test_concurrent_payments_cannot_overcollect_from_stale_snapshot(self):
		results = self.concurrent_payments([(20, "concurrent-a"), (20, "concurrent-b")])
		self.assertEqual(results.count("rejected"), 1)
		frappe.db.rollback()
		self.assertEqual(payment_summary(self.contract)["paid"], 20)

	def test_concurrent_same_request_returns_one_receipt(self):
		results = self.concurrent_payments([(10, "concurrent-same"), (10, "concurrent-same")])
		self.assertTrue(all(isinstance(row, dict) for row in results), results)
		self.assertEqual(results[0]["name"], results[1]["name"])
		self.assertEqual(sum(row["already_processed"] for row in results), 1)
