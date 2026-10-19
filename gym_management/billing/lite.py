"""Local adapter: selects authorized fiscal data and delegates calculation to Lite."""

import json
from decimal import Decimal

import frappe
from facturada_core.api.license import enforce_feature
from facturada_core.api.pos_terminal import resolve_pos_terminal_for_invoice
from facturada_core.api.tax_config import get_tax_profile
from frappe import _
from frappe.utils import nowdate

from gym_management.billing.service import PreparedDraft
from gym_management.membership_rules import money


class LiteDraftGateway:
	def prepare(self, membership, selections):
		if "facturada_lite" not in frappe.get_installed_apps():
			frappe.throw(_("Instale FacturADA Lite para preparar facturas de GYM."))
		from facturada_lite.api.invoice import build_invoice_doc

		enforce_feature("billing", business=membership.business)
		missing = [
			field
			for field in ("customer", "service", "pos_terminal", "price_basis")
			if not selections.get(field)
		]
		if missing:
			frappe.throw(_("Seleccione cliente fiscal, servicio, terminal y tratamiento del precio."))
		customer = self._owned("FacturADA Lite Customer", selections["customer"], membership.business)
		item = self._owned("FacturADA Lite Item", selections["service"], membership.business)
		if item.item_type != "Servicio" or item.track_stock:
			frappe.throw(_("Seleccione un servicio sin control de inventario."))
		profile = get_tax_profile(membership.business)
		terminal = resolve_pos_terminal_for_invoice(
			membership.business, pos_terminal=selections["pos_terminal"]
		)
		establishment = frappe.db.get_value("GYM Branch", membership.origin_branch, "establishment")
		if not terminal or not establishment or terminal.establishment != establishment:
			frappe.throw(
				_("El terminal fiscal debe corresponder al establecimiento de la sede."),
				frappe.PermissionError,
			)
		if profile.environment not in {"Pruebas", "Produccion"}:
			frappe.throw(_("Configure un ambiente fiscal válido."))
		if money(membership.total) <= 0:
			frappe.throw(_("Esta preparación requiere un contrato con importe mayor a cero."))
		tax = Decimal(str(item.tax_rate or 0))
		if not tax.is_finite() or tax < 0 or tax > 100:
			frappe.throw(_("La tarifa del servicio no es válida."))
		basis = selections["price_basis"]
		if basis not in {"Impuestos incluidos", "Impuestos no incluidos"}:
			frappe.throw(_("Seleccione explícitamente si el precio incluye impuestos."))
		factor = 1 + tax / 100 if basis == "Impuestos incluidos" else Decimal(1)
		payload = {
			"business": membership.business,
			"customer": customer.name,
			"pos_terminal": terminal.name,
			"establishment": terminal.establishment,
			"emission_point": terminal.emission_point,
			"environment": profile.environment,
			"currency": "USD",
			"posting_date": nowdate(),
			"document_type": "Factura",
			"payment_condition": "Credito",
			"payment_due_date": str(membership.payment_due_date),
			"items": [
				{
					"item": item.name,
					"qty": 1,
					"rate": str((money(membership.price) / factor).quantize(Decimal("0.000001"))),
					"discount_amount": str(money(money(membership.discount) / factor)),
					"tax_rate": str(tax),
				}
			],
			"notes": _(
				"Borrador de membresía {0}; no representa un cobro ni está habilitado para emisión."
			).format(membership.name),
		}
		doc = build_invoice_doc(dict(payload), emit=False)
		doc.run_method("validate")
		if money(doc.grand_total) != money(membership.total):
			frappe.throw(
				_(
					"El total fiscal {0} no coincide con el importe contratado {1}. Revise impuestos y redondeo; el contrato no será modificado."
				).format(doc.grand_total, membership.total)
			)
		return PreparedDraft(payload, str(money(doc.grand_total)), str(tax))

	def create(self, request, draft):
		from facturada_lite.api.invoice import create_invoice

		payload = {**draft.payload, "source_doctype": request.doctype, "source_name": request.name}
		return create_invoice(payload=payload)["data"]["name"]

	@staticmethod
	def _owned(doctype, name, business):
		if not frappe.db.exists(doctype, {"name": name, "business": business, "status": "Activo"}):
			frappe.throw(
				_("El cliente o servicio no está activo o no pertenece al negocio."), frappe.PermissionError
			)
		return frappe.get_doc(doctype, name)


class BillingRequestInvoiceSource:
	"""Guard a prepared invoice through all Lite entry points, including direct calls."""

	receipt_applications = True

	def receipt_filters(self, invoice):
		self.check(invoice, "read")
		request = frappe.get_doc("GYM Billing Request", invoice.source_name)
		return {
			"business": request.business,
			"source_doctype": "GYM Membership",
			"source_name": request.membership,
		}

	def authorize_application(self, invoice, receipt, action, user):
		from facturada_core.api.business import require_business_permission

		from gym_management.permissions import check_document, require_access, require_branch

		request = frappe.get_doc("GYM Billing Request", invoice.source_name)
		check_document(request, "read", user)
		require_business_permission(
			invoice.business, "billing.read" if action == "read" else "billing.manage", user=user
		)
		require_access(
			invoice.business, "gym.payments.cancel" if action == "cancel" else "gym.payments.read", user
		)
		require_branch(request.business, request.origin_branch, user, allow_inactive=action == "read")
		if (
			invoice.business != request.business
			or request.invoice != invoice.name
			or receipt.business != request.business
			or receipt.source_doctype != "GYM Membership"
			or receipt.source_name != request.membership
		):
			frappe.throw(
				_("El recibo y la factura deben corresponder al mismo contrato y negocio."),
				frappe.PermissionError,
			)
		if action != "read":
			enforce_feature("billing", business=request.business)

	def lock_application_origin(self, invoice):
		from gym_management.billing.service import authorized_membership
		from gym_management.permissions import check_document

		request = frappe.get_doc("GYM Billing Request", invoice.source_name)
		if request.emission_terms:
			# Technical status jobs run as Administrator and must be able to finish
			# an already numbered document even after a GYM subscription expires.
			if frappe.session.user != "Administrator":
				check_document(request, "read")
			member = frappe.db.get_value("GYM Membership", request.membership, "member")
			frappe.db.get_value("GYM Member", member, "name", for_update=True)
			frappe.db.get_value("GYM Membership", request.membership, "name", for_update=True)
		else:
			authorized_membership(request.membership, lock=True)
		frappe.db.get_value(request.doctype, request.name, "name", for_update=True)

	def query_condition(self, user):
		from gym_management.permissions import billing_invoice_query

		return billing_invoice_query(user)

	def check(self, invoice, action):
		from gym_management.billing.service import authorized_membership

		request = frappe.get_doc("GYM Billing Request", invoice.source_name)
		if action == "read":
			request.check_permission("read")
			return
		if action == "credit_note":
			request.check_permission("read")
			frappe.throw(
				_(
					"La corrección fiscal de GYM requiere un flujo vinculado de nota de crédito y conciliación; no se creará un comprobante desvinculado."
				)
			)
		from gym_management.billing.emission import in_dispatch
		from gym_management.permissions import check_document

		terms = json.loads(request.emission_terms) if request.emission_terms else None
		if terms:
			if frappe.session.user != "Administrator":
				check_document(request, "read")
		else:
			authorized_membership(request.membership, lock=invoice.is_new())
		if invoice.business != request.business:
			frappe.throw(_("La factura no pertenece al negocio de la solicitud."), frappe.PermissionError)
		if action in {"number", "emit"}:
			phase = "number" if action == "number" else "send"
			if not terms or not in_dispatch(invoice, phase):
				frappe.throw(
					_(
						"Use la emisión controlada desde la solicitud GYM; los reintentos solo consultan la clave existente."
					)
				)
			if action == "emit" and (
				not request.emission_started_at or request.emission_access_key != invoice.access_key
			):
				frappe.throw(_("Debe persistirse la identidad fiscal antes del envío."))
		if terms and request.emission_access_key and invoice.access_key != request.emission_access_key:
			frappe.throw(_("No puede cambiar la identidad fiscal de la solicitud."))
		if request.emission_identity:
			for field, expected_value in json.loads(request.emission_identity).items():
				if str(invoice.get(field) or "") != expected_value:
					frappe.throw(_("La identidad fiscal reservada es inmutable."))
		if invoice.is_new():
			request = frappe.get_doc(request.doctype, request.name, for_update=True)
		if request.invoice and request.invoice != invoice.name:
			frappe.throw(_("La solicitud ya está vinculada a otra factura."))
		existing = (
			frappe.db.get_value(
				"FacturADA Lite Invoice",
				{
					"source_doctype": request.doctype,
					"source_name": request.name,
					"name": ["!=", invoice.name],
				},
				"name",
				for_update=True,
			)
			if invoice.is_new()
			else None
		)
		if existing:
			frappe.throw(_("Esta solicitud ya tiene un borrador fiscal."))
		payload = json.loads(request.draft_payload)
		if not terms and (
			invoice.docstatus or invoice.status != "Borrador" or invoice.access_key or invoice.payments
		):
			frappe.throw(_("El borrador GYM no admite pagos, numeración ni confirmación todavía."))
		if terms:
			if invoice.docstatus == 2 or len(invoice.payments) != len(terms):
				frappe.throw(_("Las formas fiscales acordadas son inmutables."))
			for row, expected in zip(invoice.payments, terms, strict=False):
				if (
					row.payment_code != expected["payment_code"]
					or row.payment_method != expected["payment_method"]
					or money(row.amount) != money(expected["amount"])
					or row.credit_days != expected["credit_days"]
				):
					frappe.throw(_("Las formas fiscales acordadas son inmutables."))
		for field in (
			"customer",
			"pos_terminal",
			"establishment",
			"emission_point",
			"environment",
			"currency",
			"document_type",
			"payment_condition",
		):
			if invoice.get(field) != payload.get(field):
				frappe.throw(_("Las condiciones fiscales del borrador GYM son inmutables."))
		if len(invoice.items) != 1:
			frappe.throw(_("El servicio del borrador GYM es inmutable."))
		row, expected = invoice.items[0], payload["items"][0]
		if row.item != expected["item"] or Decimal(str(row.qty)) != 1 or row.discount_percentage:
			frappe.throw(_("El servicio del borrador GYM es inmutable."))
		for field in ("rate", "discount_amount", "tax_rate"):
			if Decimal(str(row.get(field))) != Decimal(str(expected[field])):
				frappe.throw(_("Los importes del borrador GYM son inmutables."))
		if money(invoice.grand_total) != money(request.invoice_total):
			frappe.throw(_("El total del borrador no coincide con la solicitud."))
