"""Thin authenticated RPC boundary; the use case lives in billing.service."""

import json

import frappe
from frappe import _

from gym_management.billing.service import INPUT_FIELDS, authorized_membership, create_request, gateway


@frappe.whitelist(methods=["POST"])
def preview_billing(membership, customer=None, service=None, pos_terminal=None, price_basis=None):
	doc = authorized_membership(membership)
	values = dict(customer=customer, service=service, pos_terminal=pos_terminal, price_basis=price_basis)
	missing = [key for key, value in values.items() if not value]
	if "facturada_lite" not in frappe.get_installed_apps():
		missing.append("facturada_lite")
	if missing:
		return {
			"ready": False,
			"missing": missing,
			"message": _("Complete la configuración fiscal antes de crear el borrador."),
		}
	draft = gateway().prepare(doc, values)
	return {
		"ready": True,
		"commercial_total": doc.total,
		"invoice_total": draft.total,
		"tax_rate": draft.tax_rate,
		"environment": draft.payload["environment"],
		"can_emit": False,
	}


@frappe.whitelist(methods=["POST"])
def prepare_billing_request(payload):
	data = json.loads(payload) if isinstance(payload, str) else payload
	if not isinstance(data, dict) or set(data) - {*INPUT_FIELDS, "request_key"}:
		frappe.throw(_("La solicitud fiscal contiene campos no permitidos."))
	frappe.db.savepoint("gym_billing_request")
	try:
		doc = create_request(data)
		return {
			"name": doc.name,
			"invoice": doc.invoice,
			"invoice_total": float(doc.invoice_total),
			"can_emit": False,
		}
	except Exception:
		frappe.db.rollback(save_point="gym_billing_request")
		raise


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def billing_link_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.utils import cint

	filters = frappe._dict(filters or {})
	membership = authorized_membership(filters.membership)
	if "facturada_lite" not in frappe.get_installed_apps():
		return []
	if doctype == "FacturADA POS Terminal":
		from facturada_core.api.pos_terminal import list_pos_terminals

		establishment = frappe.db.get_value("GYM Branch", membership.origin_branch, "establishment")
		rows = [
			[row["name"], row["terminal_name"]]
			for row in list_pos_terminals(membership.business)["data"]
			if row["establishment"] == establishment
			and txt.casefold() in (row["name"] + row["terminal_name"]).casefold()
		]
		return rows[max(cint(start), 0) : max(cint(start), 0) + min(max(cint(page_len), 1), 50)]
	name_field = {"FacturADA Lite Customer": "customer_name", "FacturADA Lite Item": "item_name"}.get(doctype)
	if not name_field:
		frappe.throw(_("Tipo de búsqueda fiscal no permitido."), frappe.PermissionError)
	conditions = {"business": membership.business, "status": "Activo"}
	if doctype == "FacturADA Lite Item":
		conditions.update(item_type="Servicio", track_stock=0)
	return frappe.get_all(
		doctype,
		filters=conditions,
		or_filters={"name": ["like", f"%{txt}%"], name_field: ["like", f"%{txt}%"]},
		fields=["name", name_field],
		as_list=True,
		limit_start=max(cint(start), 0),
		limit_page_length=min(max(cint(page_len), 1), 50),
	)


@frappe.whitelist(methods=["POST"])
def emit_billing_request(name, future_payments=None):
	from gym_management.billing.emission import emit

	try:
		payments = json.loads(future_payments) if isinstance(future_payments, str) else future_payments
	except ValueError:
		frappe.throw(_("Las condiciones fiscales deben ser una lista válida."))
	return emit(name, payments or [])


@frappe.whitelist(methods=["POST"])
def query_billing_request(name):
	from gym_management.billing.emission import query

	return query(name)


@frappe.whitelist(methods=["GET", "POST"])
def get_emission_context(name):
	from facturada_core.api.business import require_business_permission
	from facturada_core.api.license import enforce_feature
	from facturada_lite.api.payment import SRI_PAYMENT_NAMES
	from facturada_lite.payments.applications import summary

	from gym_management.permissions import check_document

	request = frappe.get_doc("GYM Billing Request", name)
	check_document(request, "read")
	invoice = frappe.get_doc("FacturADA Lite Invoice", request.invoice)
	can_manage = False
	try:
		require_business_permission(request.business, "billing.manage")
		can_manage = True
	except frappe.PermissionError:
		pass
	can_emit = can_manage and not request.emission_started_at
	if can_emit:
		try:
			enforce_feature("billing", business=request.business)
		except (frappe.PermissionError, frappe.ValidationError):
			can_emit = False
	return {
		"status": invoice.status,
		"document_number": invoice.document_number,
		"environment": request.environment,
		"summary": summary(invoice),
		"can_emit": bool(can_emit),
		"can_query": bool(can_manage and request.emission_started_at),
		"payment_codes": [
			{"value": code, "label": f"{code} · {label}"} for code, label in sorted(SRI_PAYMENT_NAMES.items())
		],
	}
