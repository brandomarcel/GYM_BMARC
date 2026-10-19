"""One durable submission intent per invoice; subsequent actions only query Lite.

emit owns its HTTP transaction: fiscal identity is committed BEFORE the provider
call. A lost response can therefore never roll back the key and trigger a resend.
"""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation

import frappe
from facturada_core.api.business import require_business_permission
from facturada_core.api.license import enforce_document_limit, enforce_feature
from facturada_core.api.tax_config import get_tax_profile
from frappe import _
from frappe.utils import cstr, now_datetime, nowdate

from gym_management.membership_rules import money
from gym_management.permissions import check_document

_dispatch = ContextVar("gym_fiscal_dispatch", default=None)


@contextmanager
def dispatch_phase(invoice, phase):
	token = _dispatch.set((invoice.name, phase))
	try:
		yield
	finally:
		_dispatch.reset(token)


def in_dispatch(invoice, phase):
	return _dispatch.get() == (invoice.name, phase)


def authorized_request(name):
	request = frappe.get_doc("GYM Billing Request", name)
	check_document(request, "read")
	require_business_permission(request.business, "billing.manage")
	return request


def lock_request(name):
	from gym_management.billing.service import authorized_membership

	request = authorized_request(name)
	authorized_membership(request.membership, lock=True)
	request = frappe.get_doc(request.doctype, name, for_update=True)
	invoice = frappe.get_doc("FacturADA Lite Invoice", request.invoice, for_update=True)
	if (invoice.business, invoice.source_doctype, invoice.source_name) != (
		request.business,
		request.doctype,
		name,
	):
		frappe.throw(_("La factura no corresponde a esta solicitud."), frappe.PermissionError)
	return request, invoice


def fiscal_payments(request, invoice, future_payments):
	from facturada_lite.api.payment import SRI_PAYMENT_CODES, normalize_sri_payment_code, payment_method_name
	from facturada_lite.api.receipts import total_received
	from facturada_lite.payments.applications import summary

	balance = summary(invoice, for_update=True)
	if money(balance["total_collected"]) != total_received(
		request.business, "GYM Membership", request.membership, for_update=True
	):
		frappe.throw(_("Aplique todos los recibos del contrato antes de preparar la emisión."))
	rows = frappe.db.sql(
		"""SELECT receipt.payment_method, app.amount
		FROM `tabFacturADA Receipt Application` app
		JOIN `tabFacturADA Payment Receipt` receipt ON receipt.name = app.receipt
		WHERE app.invoice = %s AND app.business = %s AND app.docstatus = 1 AND receipt.docstatus = 1
		ORDER BY receipt.payment_method, app.name FOR UPDATE""",
		(invoice.name, invoice.business),
		as_dict=True,
	)
	by_method = {}
	for row in rows:
		by_method[row.payment_method] = by_method.get(row.payment_method, money(0)) + money(row.amount)
	payments = [
		{
			"payment_code": normalize_sri_payment_code(payment_method=method),
			"payment_method": method,
			"amount": str(value),
			"credit_days": 0,
		}
		for method, value in by_method.items()
	]
	if not isinstance(future_payments, list) or len(future_payments) > 20:
		frappe.throw(_("Indique las formas y plazos fiscales del saldo pendiente."))
	pending = money(0)
	for row in future_payments:
		if not isinstance(row, dict) or set(row) - {"payment_code", "amount", "credit_days"}:
			frappe.throw(_("Condiciones fiscales no válidas."))
		code = cstr(row.get("payment_code"))
		try:
			days = Decimal(str(row.get("credit_days")))
			if not days.is_finite() or days != days.to_integral_value() or not 0 <= days <= 36500:
				raise ValueError
		except (InvalidOperation, ValueError):
			frappe.throw(_("Indique un plazo entero en días entre 0 y 36500."))
		value = money(row.get("amount"))
		if code not in SRI_PAYMENT_CODES or value <= 0:
			frappe.throw(_("La forma de pago y el importe pendiente no son válidos."))
		payments.append(
			{
				"payment_code": code,
				"payment_method": payment_method_name(payment_code=code),
				"amount": str(value),
				"credit_days": int(days),
			}
		)
		pending += value
	if pending != money(balance["outstanding_amount"]):
		frappe.throw(
			_("Las condiciones del saldo deben sumar exactamente {0} USD.").format(
				balance["outstanding_amount"]
			)
		)
	if sum((money(row["amount"]) for row in payments), money(0)) != money(invoice.grand_total):
		frappe.throw(_("Las formas fiscales deben cubrir el total de la factura."))
	return payments


def query(name):
	from facturada_lite.api.invoice import refresh_emission_status

	request = authorized_request(name)
	if not request.emission_started_at:
		frappe.throw(_("La factura todavía no tiene un intento de envío persistido."))
	result = refresh_emission_status(request.invoice)
	if request.emission_error:
		request.db_set("emission_error", "")
	return result


def emit(name, future_payments):
	from facturada_core.api.electronic_provider import is_provider_ready
	from facturada_lite.api.electronic_invoice import submit_lite_invoice
	from facturada_lite.api.electronic_status import plan_status_check, status_query_lock
	from facturada_lite.api.invoice import assign_electronic_identity, serialize_invoice

	initial = authorized_request(name)
	if initial.emission_started_at:
		return query(name)
	# Same lock as manual/background status: never query between the durable
	# fence and POST. This scope releases only after both explicit commits.
	with status_query_lock("FacturADA Lite Invoice", initial.invoice, transactional=False):
		frappe.db.savepoint("gym_emission_prepare")
		durable = False
		try:
			request, invoice = lock_request(name)
			if request.emission_started_at:
				return {"data": serialize_invoice(invoice), "existing": True}
			enforce_feature("billing", business=request.business)
			profile = get_tax_profile(request.business)
			if profile.environment != request.environment:
				frappe.throw(_("El ambiente del perfil cambió. Revise la solicitud fiscal antes de emitir."))
			if not is_provider_ready(profile):
				frappe.throw(
					_("Configure URL, certificado y clave del proveedor antes de reservar numeración.")
				)
			enforce_document_limit(business=request.business, environment=request.environment)
			if invoice.status != "Borrador" or invoice.access_key:
				frappe.throw(_("La factura requiere revisión; no se reservará otra identidad."))
			payments = fiscal_payments(request, invoice, future_payments)
			request.db_set(
				{
					"emission_terms": json.dumps(payments, sort_keys=True),
					"emission_requested_by": frappe.session.user,
					"emission_requested_at": now_datetime(),
					"emission_ruc": profile.ruc,
				}
			)
			invoice.set("payments", payments)
			invoice.posting_date = nowdate()
			invoice.status = "Pendiente Emision"
			with dispatch_phase(invoice, "number"):
				assign_electronic_identity(invoice, invoice.as_dict())
			request.db_set(
				{
					"emission_started_at": now_datetime(),
					"emission_access_key": invoice.access_key,
					"emission_identity": json.dumps(
						{
							field: str(invoice.get(field) or "")
							for field in (
								"access_key",
								"document_number",
								"sequential_number",
								"posting_date",
								"establishment_code",
								"emission_point_code",
							)
						}
					),
				}
			)
			invoice.status = "En Revision"
			invoice.authorization_status = "UNKNOWN"
			invoice.reception_status = "UNKNOWN"
			invoice.pending_since = now_datetime()
			plan_status_check(invoice)
			frappe.db.set_value(
				invoice.doctype,
				invoice.name,
				{
					field: invoice.get(field)
					for field in (
						"status",
						"authorization_status",
						"reception_status",
						"pending_since",
						"next_status_check_at",
						"manual_review_required",
					)
				},
			)
			# Transaction boundary is intentional and precedes every network POST.
			frappe.db.commit()
			durable = True
			request, invoice = lock_request(name)
			with dispatch_phase(invoice, "send"):
				emission = submit_lite_invoice(invoice, profile)
			frappe.db.commit()
			invoice.reload()
			return {"data": serialize_invoice(invoice), "emission": emission}
		except Exception:
			if not durable:
				frappe.db.rollback(save_point="gym_emission_prepare")
				raise
			frappe.db.rollback()
			message = _(
				"No se confirmó el resultado del envío. La clave fue conservada; consulte su estado antes de cualquier revisión."
			)
			frappe.db.set_value("GYM Billing Request", name, "emission_error", message)
			frappe.db.commit()
			frappe.throw(message)
