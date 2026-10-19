"""Allocate actual receipts using MariaDB; no SRI or duplicate cash events."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import frappe
from facturada_lite.api.collections import create_invoice_collection, recalculate_invoice_collection
from facturada_lite.api.receipt_applications import apply_receipt, get_context, reverse_application
from facturada_lite.api.receipts import cancel_receipt, record_receipt
from facturada_lite.payments import applications
from frappe.client import get, get_list
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from gym_management.api.memberships import payment_summary
from gym_management.tests import test_invoicing


class TestReceiptApplications(FrappeTestCase):
	def setUp(self):
		self.base = test_invoicing.TestInvoicing()
		self.base.setUp()
		self.addCleanup(self.base.doCleanups)
		self.business = self.base.business
		self.receipt = self.receive(15)
		self.invoice = self.base.request()["invoice"]

	def receive(self, value, **extra):
		return record_receipt(
			{
				"business": self.business,
				"source_doctype": "GYM Membership",
				"source_name": self.base.contract.name,
				"amount": value,
				"payment_method": "Transferencia",
				"reference": "TEST-ONLY",
				"request_key": frappe.generate_hash(length=32),
				**extra,
			}
		)["name"]

	def apply(self, value=15, key="apply-test", **extra):
		return apply_receipt(
			{"invoice": self.invoice, "receipt": self.receipt, "amount": value, "request_key": key, **extra}
		)

	def test_partial_then_full_allocation_preserves_one_money_ledger(self):
		contract_paid = payment_summary(self.base.contract)
		result = self.apply()
		self.assertEqual(result["summary"]["total_collected"], 15)
		self.assertEqual(result["summary"]["outstanding_amount"], 15)
		self.assertEqual(payment_summary(self.base.contract), contract_paid)
		second = self.receive(15)
		self.apply(15, "second", receipt=second)
		invoice = frappe.get_doc("FacturADA Lite Invoice", self.invoice)
		self.assertEqual(invoice.total_collected, 30)
		self.assertEqual(invoice.outstanding_amount, 0)
		self.assertEqual(invoice.collection_status, "Pagada")
		self.assertEqual(
			frappe.db.count("FacturADA Payment Receipt", {"source_name": self.base.contract.name}), 2
		)
		self.assertEqual(frappe.db.count("FacturADA Lite Invoice Collection", {"invoice": self.invoice}), 0)

	def test_retry_conflict_and_subcent_limits(self):
		first = self.apply(10)
		self.assertEqual(first["data"]["name"], self.apply(10)["data"]["name"])
		with self.assertRaises(frappe.ValidationError):
			self.apply(11)
		with self.assertRaises(frappe.ValidationError):
			self.apply(5.01, "too-much")
		self.apply(5, "remainder")
		self.assertEqual(applications.total_applied(receipt=self.receipt), 15)
		for invalid in (0, -1, "NaN", "Infinity", 0.004):
			with self.assertRaises(frappe.ValidationError):
				self.apply(invalid, str(invalid))

	def test_reversal_releases_allocation_without_refunding_receipt(self):
		result = self.apply()
		name = result["data"]["name"]
		with self.assertRaises(frappe.ValidationError):
			cancel_receipt(self.receipt, "Must reverse first")
		reversed_result = reverse_application(name, "Corrección de prueba")
		self.assertEqual(reversed_result["data"]["docstatus"], 2)
		self.assertEqual(reversed_result["summary"]["outstanding_amount"], 30)
		self.assertEqual(reverse_application(name, "Corrección de prueba")["data"]["name"], name)
		self.assertEqual(payment_summary(self.base.contract)["paid"], 15)
		self.assertEqual(self.apply()["data"]["docstatus"], 2)
		self.apply(15, "new-allocation")
		self.assertEqual(applications.total_applied(receipt=self.receipt), 15)

	def test_after_reversal_receipt_cancel_updates_contract_and_fiscal_balance(self):
		result = self.apply()
		reverse_application(result["data"]["name"], "Corrección")
		cancel_receipt(self.receipt, "Recibo ingresado por error")
		self.assertEqual(payment_summary(self.base.contract)["paid"], 0)
		invoice = frappe.get_doc("FacturADA Lite Invoice", self.invoice)
		self.assertEqual(invoice.outstanding_amount, 30)
		with self.assertRaises(frappe.ValidationError):
			self.apply(1, "cancelled-receipt")

	def test_reception_foreign_business_and_branch_revocation_are_denied(self):
		name = self.apply()["data"]["name"]
		self.base.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			self.apply(1, "reception")
		with self.assertRaises(frappe.PermissionError):
			get(applications.DOCTYPE, name)
		self.assertEqual(get_list(applications.DOCTYPE, fields=["name"]), [])
		self.base.fixture.act_as(1)
		with self.assertRaises(frappe.PermissionError):
			get_context(self.invoice)
		frappe.set_user("Administrator")
		self.base.manager()
		self.assertEqual(get(applications.DOCTYPE, name).name, name)
		frappe.set_user("Administrator")
		assignment = frappe.get_doc(
			"GYM Branch User", {"business": self.business, "user": self.base.fixture.users[0].name}
		)
		assignment.status = "Inactivo"
		assignment.save()
		self.base.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			reverse_application(name, "Revoked")
		self.assertEqual(get_list(applications.DOCTYPE, fields=["name"]), [])

	def test_crossed_contract_and_unrelated_invoice_are_rejected(self):
		from facturada_lite.api.invoice import create_invoice

		ordinary = create_invoice(
			{
				"business": self.business,
				"customer": self.base.customer.name,
				"pos_terminal": self.base.terminal.name,
				"items": [{"item": self.base.item.name, "qty": 1, "rate": 30, "tax_rate": 0}],
			}
		)["data"]["name"]
		with self.assertRaises(frappe.ValidationError):
			self.apply(invoice=ordinary)
		member = self.base.fixture.other_member
		other_contract = self.base.base.contract(member=member.name, origin_branch=member.home_branch)
		other_receipt = record_receipt(
			{
				"business": self.business,
				"source_doctype": "GYM Membership",
				"source_name": other_contract.name,
				"amount": 10,
				"payment_method": "Transferencia",
				"reference": "OTHER",
				"request_key": "other-contract",
			}
		)["name"]
		with self.assertRaises(frappe.PermissionError):
			self.apply(10, receipt=other_receipt)

	def test_generic_application_inserts_and_edits_cannot_bypass_limits(self):
		result = self.apply()
		doc = frappe.get_doc(applications.DOCTYPE, result["data"]["name"])
		doc.amount = 1
		with self.assertRaises(frappe.PermissionError):
			doc.save()
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			frappe.delete_doc(doc.doctype, doc.name)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": applications.DOCTYPE,
					"business": self.business,
					"invoice": self.invoice,
					"receipt": self.receipt,
					"amount": 1,
					"request_key": "generic",
				}
			).insert().submit()

	def test_legacy_collection_path_cannot_duplicate_receipt_income(self):
		self.apply()
		with self.assertRaises(frappe.ValidationError):
			create_invoice_collection({"invoice": self.invoice, "amount": 15})
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "FacturADA Lite Invoice Collection",
					"business": self.business,
					"invoice": self.invoice,
					"amount": 15,
					"payment_method": "Transferencia",
					"status": "Confirmado",
				}
			).insert()
		self.assertEqual(recalculate_invoice_collection(self.invoice)["total_collected"], 15)

	def test_invoice_save_and_recalculation_keep_applied_balance(self):
		self.apply(3.01)
		invoice = frappe.get_doc("FacturADA Lite Invoice", self.invoice)
		invoice.paid_amount = 999
		invoice.total_collected = 999
		invoice.outstanding_amount = 0
		invoice.save()
		invoice.reload()
		self.assertEqual(invoice.total_collected, 3.01)
		self.assertEqual(invoice.outstanding_amount, 26.99)
		self.assertEqual(recalculate_invoice_collection(invoice.name)["outstanding_amount"], 26.99)

	def test_context_lists_available_receipts_and_explicit_actor(self):
		self.base.manager()
		result = self.apply(10)
		self.assertEqual(result["data"]["applied_by"], frappe.session.user)
		context = get_context(self.invoice)
		self.assertTrue(context["can_apply"])
		self.assertEqual(context["receipts"][0]["available"], 5)
		self.assertEqual(context["summary"]["total_collected"], 10)
		self.assertEqual(len(context["applications"]), 1)
		self.assertFalse(context["can_emit"])

	def cash_receipt(self):
		subscription = frappe.get_doc("FacturADA Business Subscription", {"business": self.business})
		subscription.enable_pos = 1
		subscription.save()
		opening = frappe.get_doc(
			{
				"doctype": "FacturADA Restaurant Cash Opening",
				"business": self.business,
				"user": "Administrator",
				"pos_terminal": self.base.terminal.name,
				"opening_amount": 10,
				"opened_at": now_datetime(),
			}
		).insert()
		return opening, self.receive(15, payment_method="Efectivo", cash_opening=opening.name)

	def test_cash_counts_receipt_once_and_closed_box_blocks_reversal(self):
		from facturada_restaurante.api.frontend import close_cash_register, get_cash_payment_totals

		opening, receipt = self.cash_receipt()
		before = get_cash_payment_totals(opening)
		result = self.apply(15, "cash", receipt=receipt)
		self.assertEqual(get_cash_payment_totals(opening), before)
		close_cash_register(
			{
				"business": self.business,
				"user": "Administrator",
				"cash_opening": opening.name,
				"cash_counted": 25,
			}
		)
		with self.assertRaises(frappe.ValidationError):
			reverse_application(result["data"]["name"], "Closed box")
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			cancel_receipt(receipt, "Closed box")
		self.assertEqual(applications.total_applied(receipt=receipt), 15)

	def test_failure_after_submit_rolls_back_application_and_balance(self):
		with patch(
			"facturada_lite.payments.applications.refresh_balance",
			side_effect=frappe.ValidationError("Simulated failure"),
		):
			with self.assertRaises(frappe.ValidationError):
				self.apply()
		self.assertEqual(frappe.db.count(applications.DOCTYPE, {"invoice": self.invoice}), 0)
		self.assertEqual(
			frappe.db.get_value("FacturADA Lite Invoice", self.invoice, "outstanding_amount"), 30
		)
		self.assertTrue(self.apply()["data"]["name"])

	def test_application_files_and_share_remain_private(self):
		result = self.apply()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"application-{self.base.fixture.token}.txt",
				"is_private": 1,
				"content": self.base.fixture.token,
				"attached_to_doctype": applications.DOCTYPE,
				"attached_to_name": result["data"]["name"],
			}
		).insert()
		self.base.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			get("File", file.name)
		self.assertFalse(file.is_downloadable())
		self.assertNotIn(file.name, [row.name for row in get_list("File", fields=["name"])])
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "DocShare",
					"share_doctype": applications.DOCTYPE,
					"share_name": result["data"]["name"],
					"user": self.base.fixture.users[0].name,
					"read": 1,
				}
			).insert()

	def test_closed_cash_receipt_can_be_assigned_without_reopening_money(self):
		from facturada_restaurante.api.frontend import close_cash_register, get_cash_payment_totals

		opening, receipt = self.cash_receipt()
		close_cash_register(
			{
				"business": self.business,
				"user": "Administrator",
				"cash_opening": opening.name,
				"cash_counted": 25,
			}
		)
		before = get_cash_payment_totals(opening)
		self.apply(15, "after-closing", receipt=receipt)
		self.assertEqual(get_cash_payment_totals(opening), before)

	def cleanup_committed(self):
		frappe.set_user("Administrator")
		businesses = [doc.name for doc in self.base.fixture.businesses]
		for doctype in (applications.DOCTYPE, "FacturADA Payment Receipt"):
			frappe.db.delete(doctype, {"business": ["in", businesses]})
		self.base.cleanup_committed()

	def concurrent(self, values):
		site, sites_path = frappe.local.site, frappe.local.sites_path
		barrier = Barrier(2)
		invoice, receipt = self.invoice, self.receipt
		frappe.db.commit()
		self.addCleanup(self.cleanup_committed)

		def worker(value):
			frappe.init(site=site, sites_path=sites_path)
			frappe.connect()
			try:
				frappe.flags.in_test = True
				frappe.set_user("Administrator")
				frappe.db.count(applications.DOCTYPE)
				loaded = (
					frappe.get_doc("FacturADA Lite Invoice", invoice)
					if value.get("operation") == "save"
					else None
				)
				barrier.wait(timeout=10)
				if loaded:
					loaded.save()
					result = {"saved": True}
				elif value.get("operation") == "cancel":
					result = cancel_receipt(receipt, "Concurrent cancellation")
				else:
					result = apply_receipt({"invoice": invoice, "receipt": receipt, **value})
				frappe.db.commit()
				return result
			except frappe.ValidationError:
				frappe.db.rollback()
				return None
			finally:
				frappe.destroy()

		with ThreadPoolExecutor(max_workers=2) as pool:
			return list(pool.map(worker, values))

	def test_concurrent_retries_recover_same_application(self):
		results = self.concurrent([{"amount": 15, "request_key": "same"}] * 2)
		self.assertIsNotNone(results[0])
		self.assertIsNotNone(results[1])
		self.assertEqual(results[0]["data"]["name"], results[1]["data"]["name"])

	def test_concurrent_allocations_cannot_spend_receipt_twice(self):
		results = self.concurrent(
			[{"amount": 10, "request_key": "first"}, {"amount": 10, "request_key": "second"}]
		)
		self.assertEqual(sum(result is not None for result in results), 1)
		self.assertEqual(applications.total_applied(receipt=self.receipt, for_update=True), 10)

	def test_concurrent_invoice_save_cannot_erase_applied_balance(self):
		results = self.concurrent([{"amount": 15, "request_key": "while-saving"}, {"operation": "save"}])
		self.assertTrue(all(result is not None for result in results))
		invoice = frappe.get_doc("FacturADA Lite Invoice", self.invoice, for_update=True)
		self.assertEqual(invoice.total_collected, 15)
		self.assertEqual(invoice.outstanding_amount, 15)

	def test_concurrent_receipt_cancel_and_application_are_exclusive(self):
		results = self.concurrent(
			[{"amount": 15, "request_key": "while-cancelling"}, {"operation": "cancel"}]
		)
		self.assertEqual(sum(result is not None for result in results), 1)
		status = frappe.db.get_value("FacturADA Payment Receipt", self.receipt, "docstatus", for_update=True)
		self.assertEqual(
			applications.total_applied(receipt=self.receipt, for_update=True), 15 if status == 1 else 0
		)
