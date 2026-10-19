"""Real fiscal persistence with a mocked provider; no external emission."""

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from gym_management.api.invoicing import emit_billing_request, query_billing_request
from gym_management.tests import test_receipt_applications


class TestEmission(FrappeTestCase):
	def setUp(self):
		self.base = test_receipt_applications.TestReceiptApplications()
		self.base.setUp()
		self.addCleanup(self.base.doCleanups)
		self.addCleanup(self.cleanup_committed)
		self.billing = self.base.base
		self.business = self.billing.business
		self.invoice = self.base.invoice
		self.request = frappe.db.get_value("GYM Billing Request", {"invoice": self.invoice}, "name")
		self.base.apply()
		self.sequence = frappe.get_doc(
			{
				"doctype": "FacturADA Document Sequence",
				"business": self.business,
				"establishment": self.billing.establishment.name,
				"emission_point": self.billing.terminal.emission_point,
				"document_type": "Factura",
				"environment": "Pruebas",
				"current_number": 0,
			}
		).insert()
		self.future = [{"payment_code": "20", "amount": 15, "credit_days": 30}]
		for target, value in (
			("facturada_core.api.electronic_provider.is_provider_ready", True),
			("facturada_lite.api.electronic_invoice.is_provider_ready", True),
			("facturada_lite.api.electronic_invoice.build_certificate_payload", {}),
			("facturada_lite.api.email.queue_lite_invoice_email", {"status": "DISABLED"}),
		):
			mock = patch(target, return_value=value)
			mock.start()
			self.addCleanup(mock.stop)
		self.post = patch("facturada_lite.api.electronic_invoice.emit_invoice")
		self.provider = self.post.start()
		self.addCleanup(self.post.stop)
		self.provider.return_value = {
			"status": "AUTHORIZED",
			"authorization": {"number": "TEST-ONLY", "date": "2026-10-17T10:00:00"},
		}

	def cleanup_committed(self):
		frappe.set_user("Administrator")
		frappe.db.delete("FacturADA Document Sequence", {"business": self.base.business})
		self.base.cleanup_committed()

	def emit(self):
		return emit_billing_request(self.request, self.future)

	def test_authorization_then_retry_keeps_identity_and_one_income(self):
		result = self.emit()
		self.assertEqual(result["data"]["status"], "Autorizada")
		key = result["data"]["electronic"]["access_key"]
		self.assertEqual(len(key), 49)
		self.assertEqual(self.emit()["data"]["electronic"]["access_key"], key)
		self.assertEqual(query_billing_request(self.request)["data"]["status"], "Autorizada")
		self.provider.assert_called_once()
		self.sequence.reload()
		self.assertEqual(self.sequence.current_number, 1)
		self.assertEqual(frappe.db.count("FacturADA Payment Receipt", {"business": self.business}), 1)
		doc = frappe.get_doc("FacturADA Lite Invoice", self.invoice)
		self.assertEqual(doc.total_collected, 15)
		self.assertEqual(doc.outstanding_amount, 15)
		payload = self.provider.call_args.args[0]
		self.assertEqual(payload["infoFactura"]["pagos"][-1]["plazo"], 30)

	def test_lost_response_preserves_fence_before_post_and_retry_queries(self):
		self.fence_seen = False

		def fail(*args):
			# A second independent connection must see the durable intent at POST time.
			from frappe.database import get_db

			other = get_db(
				socket=frappe.conf.db_socket,
				host=frappe.conf.db_host,
				port=frappe.conf.db_port,
				user=frappe.conf.db_name,
				password=frappe.conf.db_password,
				cur_db_name=frappe.conf.db_name,
			)
			try:
				row = other.sql(
					"SELECT emission_access_key, emission_started_at FROM `tabGYM Billing Request` WHERE name=%s",
					self.request,
				)[0]
				self.assertEqual(len(row[0]), 49)
				self.assertTrue(row[1])
				self.fence_seen = True
			finally:
				other.close()
			raise ConnectionError("test lost response")

		self.provider.side_effect = fail
		with self.assertRaises(frappe.ValidationError):
			self.emit()
		self.assertTrue(self.fence_seen)
		request = frappe.get_doc("GYM Billing Request", self.request)
		self.assertEqual(len(request.emission_access_key), 49)
		with patch(
			"facturada_lite.api.electronic_status.get_invoice_status", return_value={"status": "AUTHORIZED"}
		) as query:
			result = self.emit()
			self.assertEqual(result["data"]["electronic"]["access_key"], request.emission_access_key)
			self.assertEqual(result["data"]["status"], "Autorizada")
			query.assert_called_once()
		self.provider.assert_called_once()

	def test_invalid_terms_unapplied_money_and_missing_provider_do_not_number(self):
		for future in (
			[],
			[{"payment_code": "99", "amount": 15, "credit_days": 0}],
			[{"payment_code": "20", "amount": 15, "credit_days": -1}],
			[{"payment_code": "20", "amount": 14, "credit_days": 30}],
		):
			with self.assertRaises(frappe.ValidationError):
				emit_billing_request(self.request, future)
		with patch("facturada_core.api.electronic_provider.is_provider_ready", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				self.emit()
		self.base.receive(1)
		with self.assertRaises(frappe.ValidationError):
			self.emit()
		self.provider.assert_not_called()
		self.sequence.reload()
		self.assertEqual(self.sequence.current_number, 0)
		self.assertFalse(frappe.db.get_value("GYM Billing Request", self.request, "emission_started_at"))

	def test_generic_routes_cannot_emit_or_mutate_reserved_identity(self):
		from facturada_lite.api.electronic_invoice import submit_lite_invoice
		from facturada_lite.api.invoice import assign_electronic_identity

		doc = frappe.get_doc("FacturADA Lite Invoice", self.invoice)
		with self.assertRaises(frappe.ValidationError):
			assign_electronic_identity(doc, {})
		with self.assertRaises(frappe.ValidationError):
			submit_lite_invoice(doc, self.billing.profile)
		self.emit()
		for field, value in (
			("access_key", "0" * 49),
			("posting_date", "2026-01-01"),
			("document_number", "001-001-999999999"),
		):
			doc = frappe.get_doc("FacturADA Lite Invoice", self.invoice)
			doc.set(field, value)
			with self.assertRaises(frappe.ValidationError):
				doc.save()
		doc.reload()
		terms = json.loads(frappe.db.get_value("GYM Billing Request", self.request, "emission_terms"))
		self.assertEqual(len(terms), 2)

	def test_reception_and_other_business_are_denied_before_network(self):
		for index in (0, 1):
			self.billing.fixture.act_as(index)
			with self.assertRaises(frappe.PermissionError):
				self.emit()
			with self.assertRaises(frappe.PermissionError):
				query_billing_request(self.request)
		self.provider.assert_not_called()

	def test_pending_43_70_and_rejection_only_query_on_retry(self):
		self.provider.return_value = {"status": "PROCESSING", "code": "70", "message": "En procesamiento"}
		self.emit()
		key = frappe.db.get_value("FacturADA Lite Invoice", self.invoice, "access_key")
		with patch("facturada_lite.api.electronic_status.get_invoice_status") as query:
			for response in (
				{"status": "PROCESSING", "code": "43", "message": "Clave registrada"},
				{"status": "PROCESSING", "code": "70", "message": "En procesamiento"},
				{"status": "NOT_AUTHORIZED", "message": "Rechazo de prueba"},
			):
				frappe.cache().delete_value(
					f"facturada:last-status-query:FacturADA Lite Invoice:{self.invoice}"
				)
				query.return_value = response
				self.emit()
				frappe.db.commit()
				self.assertEqual(
					frappe.db.get_value("FacturADA Lite Invoice", self.invoice, "access_key"), key
				)
			self.assertEqual(query.call_count, 3)
		self.provider.assert_called_once()
		self.assertEqual(frappe.db.get_value("FacturADA Lite Invoice", self.invoice, "status"), "Rechazada")

	def test_future_collection_and_master_edits_preserve_fiscal_snapshot(self):
		self.emit()
		before = frappe.get_doc("FacturADA Lite Invoice", self.invoice)
		self.billing.item.item_name = "Nombre nuevo"
		self.billing.item.status = "Inactivo"
		self.billing.item.save()
		self.billing.customer.customer_name = "Nombre nuevo"
		self.billing.customer.status = "Inactivo"
		self.billing.customer.save()
		receipt = self.base.receive(15)
		self.base.apply(15, "future", receipt=receipt)
		after = frappe.get_doc("FacturADA Lite Invoice", self.invoice)
		after.save()
		after.reload()
		self.assertEqual(after.customer_name, before.customer_name)
		self.assertEqual(after.items[0].item_name, before.items[0].item_name)
		self.assertEqual(after.outstanding_amount, 0)
		self.assertEqual(after.payments[-1].credit_days, 30)

	def test_printing_query_and_context_respect_revoked_branch(self):
		from facturada_lite.api.printing import download_lite_invoice_pdf, download_lite_invoice_xml

		from gym_management.api.invoicing import get_emission_context

		self.emit()
		self.billing.manager()
		self.assertTrue(get_emission_context(self.request)["can_query"])
		frappe.set_user("Administrator")
		assignment = frappe.get_doc(
			"GYM Branch User", {"business": self.business, "user": self.billing.fixture.users[0].name}
		)
		assignment.status = "Inactivo"
		assignment.save()
		self.billing.fixture.act_as()
		with (
			patch("frappe.get_print") as printer,
			patch("facturada_lite.api.electronic_status.get_invoice_status") as query,
		):
			for operation in (
				lambda: download_lite_invoice_pdf(invoice_name=self.invoice),
				lambda: download_lite_invoice_xml(invoice_name=self.invoice),
				lambda: query_billing_request(self.request),
				lambda: get_emission_context(self.request),
			):
				with self.assertRaises(frappe.PermissionError):
					operation()
			printer.assert_not_called()
			query.assert_not_called()

	def test_manager_emits_fully_paid_without_inventing_pending_payments(self):
		receipt = self.base.receive(15)
		self.base.apply(15, "remaining", receipt=receipt)
		self.billing.manager()
		result = emit_billing_request(self.request, [])
		self.assertEqual(result["data"]["status"], "Autorizada")
		self.assertEqual(result["data"]["totals"]["outstanding_amount"], 0)
		self.provider.assert_called_once()

	def test_scheduled_status_can_finish_after_gym_feature_expires(self):
		from facturada_lite.api.electronic_status import synchronize_status
		from frappe.utils import add_to_date, now_datetime

		self.provider.return_value = {"status": "PROCESSING", "code": "70"}
		self.emit()
		frappe.db.set_value("FacturADA Business Subscription", {"business": self.business}, "enable_gym", 0)
		frappe.db.set_value(
			"FacturADA Lite Invoice",
			self.invoice,
			"next_status_check_at",
			add_to_date(now_datetime(), minutes=-1),
		)
		with patch(
			"facturada_lite.api.electronic_status.get_invoice_status",
			return_value={
				"status": "AUTHORIZED",
				"authorization": {"number": "TEST", "date": "2026-10-17T10:00:00"},
			},
		) as query:
			result = synchronize_status("FacturADA Lite Invoice", self.invoice, automatic=True)
			self.assertEqual(result[0].status, "Autorizada")
			query.assert_called_once()
		self.provider.assert_called_once()

	def test_new_generic_request_cannot_inject_emission_metadata(self):
		member = self.billing.fixture.other_member
		contract = self.billing.base.contract(member=member.name, origin_branch=member.home_branch)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "GYM Billing Request",
					**self.billing.values,
					"membership": contract.name,
					"request_key": "forged",
					"emission_started_at": "2026-10-17 10:00:00",
				}
			).insert()
		self.provider.assert_not_called()

	def test_generic_credit_note_cannot_detach_fiscal_correction_from_contract(self):
		from facturada_lite.api.invoice import create_credit_note_from_invoice

		self.emit()
		with self.assertRaises(frappe.ValidationError):
			create_credit_note_from_invoice(self.invoice)
		self.assertEqual(frappe.db.count("FacturADA Lite Invoice", {"business": self.business}), 1)

	def test_concurrent_retry_during_post_cannot_send_or_query_again(self):
		site, sites_path = frappe.local.site, frappe.local.sites_path
		request_name, future = self.request, self.future
		response = self.provider.return_value

		def retry():
			frappe.init(site=site, sites_path=sites_path)
			frappe.connect()
			try:
				frappe.set_user("Administrator")
				with self.assertRaises(frappe.ValidationError):
					emit_billing_request(request_name, future)
			finally:
				frappe.db.rollback()
				frappe.destroy()

		def post(*args):
			with ThreadPoolExecutor(max_workers=1) as pool:
				pool.submit(retry).result(timeout=10)
			return response

		self.provider.side_effect = post
		with patch("facturada_lite.api.electronic_status.get_invoice_status") as query:
			self.emit()
			query.assert_not_called()
		self.provider.assert_called_once()
