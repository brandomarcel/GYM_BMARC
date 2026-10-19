"""Real database integration for preparation; never contacts a fiscal provider."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import frappe
from frappe.client import get, get_list
from frappe.tests.utils import FrappeTestCase

from gym_management.api.invoicing import billing_link_query, prepare_billing_request, preview_billing
from gym_management.api.memberships import payment_summary
from gym_management.tests import test_memberships


class TestInvoicing(FrappeTestCase):
	def setUp(self):
		self.base = test_memberships.TestMemberships()
		self.base.setUp()
		self.addCleanup(self.base.doCleanups)
		self.fixture = self.base.fixture
		self.contract = self.base.contract()
		self.business = self.base.business
		subscription = frappe.get_doc("FacturADA Business Subscription", {"business": self.business})
		subscription.enable_billing = 1
		subscription.save()
		self.customer = frappe.get_doc(
			{
				"doctype": "FacturADA Lite Customer",
				"business": self.business,
				"customer_name": "Pagador de prueba",
				"identification_type": "Consumidor Final",
				"identification_number": "9999999999999",
			}
		).insert()
		self.item = frappe.get_doc(
			{
				"doctype": "FacturADA Lite Item",
				"business": self.business,
				"item_name": "Servicio de gimnasio",
				"item_type": "Servicio",
				"tax_rate": 15,
				"standard_rate": 100,
			}
		).insert()
		self.establishment = frappe.get_doc(
			{
				"doctype": "FacturADA Establishment",
				"business": self.business,
				"establishment_code": "001",
				"establishment_name": "Sede fiscal",
			}
		).insert()
		point = frappe.get_doc(
			{
				"doctype": "FacturADA Emission Point",
				"business": self.business,
				"establishment": self.establishment.name,
				"emission_point_code": "001",
				"emission_point_name": "Emisión de prueba",
			}
		).insert()
		self.terminal = frappe.get_doc(
			{
				"doctype": "FacturADA POS Terminal",
				"business": self.business,
				"establishment": self.establishment.name,
				"emission_point": point.name,
				"terminal_name": "Terminal de prueba",
			}
		).insert()
		self.profile = frappe.get_doc(
			{
				"doctype": "FacturADA Tax Profile",
				"business": self.business,
				"ruc": self.fixture.businesses[0].tax_id,
				"legal_name": "Negocio sintético",
				"main_address": "Dirección de prueba",
				"environment": "Pruebas",
			}
		).insert()
		branch = frappe.get_doc("GYM Branch", self.base.branch)
		branch.establishment = self.establishment.name
		branch.save()
		self.values = dict(
			membership=self.contract.name,
			customer=self.customer.name,
			service=self.item.name,
			pos_terminal=self.terminal.name,
			price_basis="Impuestos incluidos",
			request_key="fiscal-test",
		)

	def request(self, **values):
		return prepare_billing_request({**self.values, **values})

	def manager(self):
		frappe.set_user("Administrator")
		assignment = frappe.get_doc(
			"FacturADA Business User", {"business": self.business, "user": self.fixture.users[0].name}
		)
		assignment.business_role = "Gerente"
		assignment.save()
		self.fixture.act_as()

	def test_preview_has_no_persistence_or_fiscal_side_effects(self):
		before = frappe.db.count("FacturADA Lite Invoice")
		missing = preview_billing(self.contract.name)
		self.assertFalse(missing["ready"])
		self.assertIn("price_basis", missing["missing"])
		with (
			patch("facturada_core.api.tax_config.reserve_document_number") as reserve,
			patch("facturada_core.api.electronic_provider.emit_invoice") as provider,
		):
			result = preview_billing(**{k: v for k, v in self.values.items() if k != "request_key"})
			self.assertTrue(result["ready"])
			self.assertEqual(float(result["invoice_total"]), 30)
			self.assertFalse(result["can_emit"])
			reserve.assert_not_called()
			provider.assert_not_called()
		self.assertEqual(frappe.db.count("FacturADA Lite Invoice"), before)

	def test_manager_creates_one_draft_without_collecting_or_numbering(self):
		self.manager()
		paid = payment_summary(self.contract)
		result = self.request()
		self.assertFalse(result["can_emit"])
		request = get("GYM Billing Request", result["name"])
		self.assertEqual(request.prepared_by, frappe.session.user)
		self.assertEqual(float(request.invoice_total), 30)
		self.assertEqual(self.request()["invoice"], result["invoice"])
		self.assertEqual(self.request(request_key="another-retry")["invoice"], result["invoice"])
		invoice = frappe.get_doc("FacturADA Lite Invoice", result["invoice"])
		self.assertEqual(invoice.status, "Borrador")
		self.assertFalse(invoice.access_key)
		self.assertEqual(len(invoice.payments), 0)
		self.assertEqual(invoice.source_name, request.name)
		self.assertEqual(payment_summary(self.contract), paid)
		self.assertEqual(frappe.db.count("FacturADA Payment Receipt", {"source_name": self.contract.name}), 0)

	def test_reception_and_other_branch_cannot_prepare_or_read_requests(self):
		result = self.request()
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			self.request()
		with self.assertRaises(frappe.PermissionError):
			get("GYM Billing Request", result["name"])
		self.assertEqual(get_list("GYM Billing Request", fields=["name"]), [])
		self.manager()
		frappe.set_user("Administrator")
		assignment = frappe.get_doc(
			"GYM Branch User", {"business": self.business, "user": self.fixture.users[0].name}
		)
		assignment.status = "Inactivo"
		assignment.save()
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			self.request()
		self.assertEqual(get_list("GYM Billing Request", fields=["name"]), [])

	def test_other_business_and_crossed_links_are_denied(self):
		result = self.request()
		self.fixture.act_as(1)
		with self.assertRaises(frappe.PermissionError):
			get("GYM Billing Request", result["name"])
		with self.assertRaises(frappe.PermissionError):
			self.request()
		frappe.set_user("Administrator")
		foreign = frappe.get_doc(
			{
				"doctype": "FacturADA Lite Customer",
				"business": self.fixture.businesses[1].name,
				"customer_name": "Otro pagador",
				"identification_type": "Consumidor Final",
				"identification_number": "9999999999999",
			}
		).insert()
		# A conflicting replay must fail even when the new customer is valid elsewhere.
		with self.assertRaises(frappe.ValidationError):
			self.request(customer=foreign.name)

	def test_requests_are_immutable_and_generic_inserts_validate(self):
		result = self.request()
		doc = frappe.get_doc("GYM Billing Request", result["name"])
		doc.invoice_total = 1
		with self.assertRaises(frappe.PermissionError):
			doc.save()
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(doc.doctype, doc.name)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "GYM Billing Request",
					"business": self.business,
					"origin_branch": self.base.branch,
					**self.values,
				}
			).insert()
		with self.assertRaises(frappe.ValidationError):
			self.request(invoice="injected")

	def test_price_mismatch_rolls_back_and_does_not_change_contract(self):
		with self.assertRaises(frappe.ValidationError):
			self.request(price_basis="Impuestos no incluidos")
		self.assertEqual(frappe.db.count("GYM Billing Request", {"membership": self.contract.name}), 0)
		self.contract.reload()
		self.assertEqual(self.contract.total, 30)
		self.assertEqual(self.request()["invoice_total"], 30)

	def test_discounted_and_tax_free_contracts_match_lite_totals(self):
		self.contract.cancel()
		self.contract = self.base.contract(discount=5, discount_reason="Prueba autorizada")
		self.values["membership"] = self.contract.name
		self.item.tax_rate = 0
		self.item.save()
		result = self.request(price_basis="Impuestos no incluidos")
		invoice = frappe.get_doc("FacturADA Lite Invoice", result["invoice"])
		self.assertEqual(invoice.grand_total, 25)
		self.assertEqual(invoice.total_discount, 5)

	def test_bad_service_and_wrong_terminal_are_rejected(self):
		self.item.item_type = "Producto"
		self.item.save()
		with self.assertRaises(frappe.ValidationError):
			self.request()
		self.item.item_type = "Servicio"
		self.item.save()
		branch = frappe.get_doc("GYM Branch", self.base.branch)
		branch.establishment = None
		branch.save()
		with self.assertRaises(frappe.PermissionError):
			self.request()

	def test_missing_lite_feature_and_tax_profile_fail_closed(self):
		with patch(
			"gym_management.billing.lite.frappe.get_installed_apps",
			return_value=["frappe", "facturada_core", "gym_management"],
		):
			with self.assertRaises(frappe.ValidationError):
				self.request()
		sub = frappe.get_doc("FacturADA Business Subscription", {"business": self.business})
		sub.enable_billing = 0
		sub.save()
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			self.request()
		sub.enable_billing = 1
		sub.save()
		self.profile.status = "Inactivo"
		self.profile.save()
		with self.assertRaises(frappe.ValidationError):
			self.request()

	def test_saved_draft_blocks_all_emission_entry_points_before_effects(self):
		from facturada_lite.api.electronic_invoice import submit_lite_invoice
		from facturada_lite.api.invoice import assign_electronic_identity

		result = self.request()
		invoice = frappe.get_doc("FacturADA Lite Invoice", result["invoice"])
		with (
			patch("facturada_lite.api.invoice.reserve_document_number") as reserve,
			patch("facturada_lite.api.electronic_invoice.emit_invoice") as emit,
		):
			with self.assertRaises(frappe.ValidationError):
				assign_electronic_identity(invoice, invoice.as_dict())
			with self.assertRaises(frappe.ValidationError):
				submit_lite_invoice(invoice, self.profile)
			reserve.assert_not_called()
			emit.assert_not_called()
		invoice.source_doctype = None
		invoice.source_name = None
		with self.assertRaises(frappe.PermissionError):
			invoice.save()

	def test_cloning_and_editing_draft_conditions_are_denied(self):
		result = self.request()
		invoice = frappe.get_doc("FacturADA Lite Invoice", result["invoice"])
		clone = frappe.copy_doc(invoice)
		with self.assertRaises(frappe.ValidationError):
			clone.insert()
		invoice.items[0].rate = 1
		with self.assertRaises(frappe.ValidationError):
			invoice.save()

	def test_failed_invoice_insert_rolls_back_request(self):
		with patch(
			"gym_management.billing.lite.LiteDraftGateway.create",
			side_effect=frappe.ValidationError("Simulated failure"),
		):
			with self.assertRaises(frappe.ValidationError):
				self.request()
		self.assertEqual(frappe.db.count("GYM Billing Request", {"membership": self.contract.name}), 0)
		self.assertTrue(self.request()["invoice"])

	def test_search_uses_membership_scope_and_only_services(self):
		rows = billing_link_query(
			"FacturADA Lite Item", "", "name", 0, 20, {"membership": self.contract.name}
		)
		self.assertEqual([row[0] for row in rows], [self.item.name])
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			billing_link_query(
				"FacturADA Lite Customer", "", "name", 0, 20, {"membership": self.contract.name}
			)

	def test_invoice_files_and_shares_keep_request_scope(self):
		result = self.request()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"fiscal-{self.fixture.token}.txt",
				"is_private": 1,
				"content": self.fixture.token,
				"attached_to_doctype": "FacturADA Lite Invoice",
				"attached_to_name": result["invoice"],
			}
		).insert()
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			get("File", file.name)
		self.assertNotIn(file.name, [row.name for row in get_list("File", fields=["name"])])
		self.assertFalse(file.is_downloadable())
		frappe.set_user("Administrator")
		file.reload()
		file.is_private = 0
		with self.assertRaises(frappe.PermissionError):
			file.save()
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "DocShare",
					"share_doctype": "FacturADA Lite Invoice",
					"share_name": result["invoice"],
					"user": self.fixture.users[0].name,
					"read": 1,
				}
			).insert()

	def test_fiscal_reads_require_gym_scope_and_replay_uses_snapshot(self):
		from facturada_lite.api.collections import get_invoice_receivables
		from facturada_lite.api.invoice import get_invoice_detail, list_invoices

		result = self.request()
		plan = frappe.get_doc("GYM Membership Plan", self.contract.plan)
		plan.price = 99
		plan.save()
		self.item.tax_rate = 0
		self.item.save()
		self.assertEqual(self.request()["invoice"], result["invoice"])
		invoice = frappe.get_doc("FacturADA Lite Invoice", result["invoice"])
		self.assertEqual(invoice.grand_total, 30)
		self.assertEqual(invoice.items[0].tax_rate, 15)
		self.manager()
		self.assertEqual(list_invoices(business=self.business)["total"], 1)
		self.assertEqual(get_invoice_receivables(business=self.business, only_open=0)["total"], 1)
		frappe.set_user("Administrator")
		assignment = frappe.get_doc(
			"GYM Branch User", {"business": self.business, "user": self.fixture.users[0].name}
		)
		assignment.status = "Inactivo"
		assignment.save()
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			get_invoice_detail(result["invoice"])
		self.assertEqual(list_invoices(business=self.business)["total"], 0)
		self.assertEqual(get_invoice_receivables(business=self.business, only_open=0)["total"], 0)
		self.assertNotIn(
			result["invoice"], [row.name for row in get_list("FacturADA Lite Invoice", fields=["name"])]
		)

	def test_source_scope_preserves_ordinary_invoices_and_pagination(self):
		from facturada_lite.api.invoice import create_invoice, list_invoices

		self.request()
		ordinary = create_invoice(
			{
				"business": self.business,
				"customer": self.customer.name,
				"pos_terminal": self.terminal.name,
				"payment_condition": "Credito",
				"items": [{"item": self.item.name, "qty": 1, "rate": 15, "tax_rate": 0}],
			}
		)["data"]["name"]
		self.manager()
		first = list_invoices(business=self.business, limit=1)
		second = list_invoices(business=self.business, limit=1, offset=1)
		self.assertEqual(first["total"], 2)
		self.assertTrue(first["has_next"])
		self.assertFalse(second["has_next"])
		self.assertNotEqual(first["data"][0].name, second["data"][0].name)
		frappe.set_user("Administrator")
		assignment = frappe.get_doc(
			"GYM Branch User", {"business": self.business, "user": self.fixture.users[0].name}
		)
		assignment.status = "Inactivo"
		assignment.save()
		self.fixture.act_as()
		remaining = list_invoices(business=self.business)
		self.assertEqual(remaining["total"], 1)
		self.assertEqual(remaining["data"][0].name, ordinary)

	def test_cross_business_service_is_denied_before_any_request_exists(self):
		foreign = frappe.get_doc(
			{
				"doctype": "FacturADA Lite Item",
				"business": self.fixture.businesses[1].name,
				"item_name": "Servicio ajeno",
				"item_type": "Servicio",
			}
		).insert()
		with self.assertRaises(frappe.PermissionError):
			self.request(service=foreign.name)
		self.assertEqual(frappe.db.count("GYM Billing Request", {"membership": self.contract.name}), 0)

	def cleanup_committed(self):
		frappe.set_user("Administrator")
		businesses = [b.name for b in self.fixture.businesses]
		for doctype in (
			"FacturADA Lite Invoice",
			"GYM Billing Request",
			"FacturADA Lite Customer",
			"FacturADA Lite Item",
			"FacturADA POS Terminal",
			"FacturADA Emission Point",
			"FacturADA Establishment",
			"FacturADA Tax Profile",
			"GYM Membership",
			"GYM Membership Plan",
			"GYM Member",
			"GYM Branch User",
			"GYM Branch",
			"FacturADA Business User",
			"FacturADA Business Subscription",
			"FacturADA Business",
		):
			filters = (
				{"name": ["in", businesses]}
				if doctype == "FacturADA Business"
				else {"business": ["in", businesses]}
			)
			names = frappe.get_all(doctype, filters=filters, pluck="name")
			for df in frappe.get_meta(doctype).get_table_fields():
				if names:
					frappe.db.delete(df.options, {"parent": ["in", names], "parenttype": doctype})
			frappe.db.delete(doctype, filters)
		for user in self.fixture.users:
			frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)
		frappe.db.commit()

	def test_concurrent_snapshots_create_only_one_invoice(self):
		site, sites_path = frappe.local.site, frappe.local.sites_path
		values = dict(self.values)
		barrier = Barrier(2)
		frappe.db.commit()
		self.addCleanup(self.cleanup_committed)

		def create_from_connection(index):
			frappe.init(site=site, sites_path=sites_path)
			frappe.connect()
			try:
				frappe.flags.in_test = True
				frappe.set_user("Administrator")
				frappe.db.count("GYM Billing Request")
				barrier.wait(timeout=10)
				result = prepare_billing_request({**values, "request_key": f"parallel-{index}"})
				frappe.db.commit()
				return result
			except Exception:
				frappe.db.rollback()
				raise
			finally:
				frappe.destroy()

		with ThreadPoolExecutor(max_workers=2) as pool:
			results = list(pool.map(create_from_connection, range(2)))
		self.assertEqual(results[0]["invoice"], results[1]["invoice"])
		self.assertEqual(results[0]["name"], results[1]["name"])
