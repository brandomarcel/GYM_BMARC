import json

import frappe
from facturada_core.api.business import has_business_permission
from frappe import _
from frappe.utils import add_days, cint, cstr, getdate, now_datetime, nowdate

from gym_management.membership_rules import money, request_hash
from gym_management.permissions import check_document, require_access, require_branch


@frappe.whitelist(methods=["POST"])
def create_membership(payload):
	data = frappe._dict(json.loads(payload) if isinstance(payload, str) else payload)
	member = frappe.get_doc("GYM Member", data.member)
	member.check_permission("read")
	require_access(data.business, "gym.memberships.manage")
	require_branch(data.business, data.origin_branch)
	if member.business != data.business:
		frappe.throw(_("El socio no pertenece al negocio."), frappe.PermissionError)
	key = cstr(data.request_key).strip()
	if not key or len(key) > 100:
		frappe.throw(_("Indique una clave de reintento de hasta 100 caracteres."))
	fields = {
		name: data.get(name)
		for name in (
			"business",
			"member",
			"plan",
			"origin_branch",
			"previous_membership",
			"start_date",
			"payment_due_date",
			"discount",
			"discount_reason",
			"promotion",
		)
	}
	fields["discount"] = str(money(fields["discount"]))
	fingerprint = request_hash(fields)
	frappe.db.get_value("GYM Member", member.name, "name", for_update=True)
	existing = frappe.db.get_value(
		"GYM Membership", {"business": data.business, "request_key": key}, "name", for_update=True
	)
	if existing:
		doc = frappe.get_doc("GYM Membership", existing, for_update=True)
		doc.check_permission("read")
		if doc.request_hash != fingerprint:
			frappe.throw(_("La clave ya fue usada para una contratación diferente."))
		return {"name": doc.name, "already_processed": True}
	doc = frappe.get_doc(
		{"doctype": "GYM Membership", **fields, "request_key": key, "request_hash": fingerprint}
	)
	doc.insert()
	return {"name": doc.name, "already_processed": False}


def payment_summary(membership, for_update=False):
	paid = money(0)
	if "facturada_lite" in frappe.get_installed_apps() and frappe.db.exists(
		"DocType", "FacturADA Payment Receipt"
	):
		from facturada_lite.api.receipts import total_received

		paid = total_received(membership.business, "GYM Membership", membership.name, for_update=for_update)
	total = money(membership.total)
	return {"paid": paid, "outstanding": max(total - paid, money(0)), "total": total}


@frappe.whitelist(methods=["GET", "POST"])
def get_membership_summary(name):
	doc = frappe.get_doc("GYM Membership", name)
	doc.check_permission("read")
	return {
		**payment_summary(doc),
		"can_record_payment": has_business_permission(doc.business, "gym.payments.record")
		and "facturada_lite" in frappe.get_installed_apps(),
		"can_approve_credit": has_business_permission(doc.business, "gym.credit.approve"),
		"can_cancel_payment": has_business_permission(doc.business, "gym.payments.cancel"),
		"can_prepare_invoice": has_business_permission(doc.business, "billing.create")
		and "facturada_lite" in frappe.get_installed_apps(),
		"billing_request": frappe.db.get_value("GYM Billing Request", {"membership": doc.name}, "name")
		if has_business_permission(doc.business, "billing.read")
		else None,
	}


@frappe.whitelist(methods=["GET", "POST"])
def find_access_member(business, branch, member_code):
	require_access(business, "gym.attendance.record")
	require_branch(business, branch)
	row = frappe.db.get_value(
		"GYM Member",
		{"business": business, "member_code": cstr(member_code).strip().upper()},
		["name", "full_name"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("No se encontró el socio en este negocio."))
	return row


@frappe.whitelist(methods=["POST"])
def approve_credit(name, reason, approved=1):
	doc = frappe.get_doc("GYM Membership", name)
	check_document(doc, "write")
	require_access(doc.business, "gym.credit.approve")
	if doc.docstatus != 1:
		frappe.throw(_("El contrato debe estar confirmado."))
	doc.credit_approved = 1 if cint(approved) else 0
	doc.credit_reason = cstr(reason).strip()
	doc.save()
	return {"name": doc.name, "credit_approved": doc.credit_approved}


def evaluate_access(business, branch, member, at_date=None, for_update=False):
	"""Internal evaluator. Public entry points must authorize the target branch first."""
	date = getdate(at_date or nowdate())
	if not frappe.db.exists("GYM Member", {"name": member, "business": business, "status": "Activo"}):
		return {"result": "Denegado", "reason": "Socio no disponible", "membership": None}
	name = frappe.db.get_value(
		"GYM Membership",
		{
			"business": business,
			"member": member,
			"docstatus": 1,
			"start_date": ["<=", date],
			"end_date": [">=", date],
		},
		"name",
		order_by="start_date desc",
		for_update=for_update,
	)
	if not name:
		return {"result": "Denegado", "reason": "Sin membresía vigente", "membership": None}
	doc = frappe.get_doc("GYM Membership", name, for_update=for_update)
	allowed = doc.access_mode == "Todas las sedes" or (
		branch == doc.origin_branch
		if doc.access_mode == "Una sede"
		else branch in {r.branch for r in doc.branches}
	)
	result = {"result": "Denegado", "reason": "Sede no incluida", "membership": doc.name}
	if not allowed:
		return result
	summary = payment_summary(doc, for_update=for_update)
	paid, total = summary["paid"], summary["total"]
	minimum = money(total * money(doc.minimum_percentage) / 100)
	if total > 0 and doc.payment_policy == "Abonos":
		minimum = max(minimum, money("0.01"))
	eligible = (
		paid >= total
		or (doc.payment_policy == "Abonos" and paid >= minimum)
		or (doc.payment_policy == "Credito" and doc.credit_approved)
	)
	if not eligible:
		result["reason"] = "Pago mínimo o crédito pendiente"
		return result
	if summary["outstanding"] > 0 and date > getdate(add_days(doc.payment_due_date, cint(doc.grace_days))):
		result["reason"] = "Deuda vencida"
		return result
	return {"result": "Permitido", "reason": "Membresía habilitada", "membership": doc.name}


@frappe.whitelist(methods=["GET", "POST"])
def check_access(business, branch, member):
	require_access(business, "gym.attendance.record")
	require_branch(business, branch)
	return evaluate_access(business, branch, member)


@frappe.whitelist(methods=["POST"])
def record_attendance(business, branch, member, request_key):
	require_access(business, "gym.attendance.record")
	require_branch(business, branch)
	if not frappe.db.exists("GYM Member", {"name": member, "business": business}):
		frappe.throw(_("Socio no disponible."), frappe.PermissionError)
	frappe.db.get_value("GYM Member", member, "name", for_update=True)
	key = cstr(request_key).strip()
	if not key or len(key) > 100:
		frappe.throw(_("Indique una clave de reintento válida."))
	existing = frappe.db.get_value(
		"GYM Attendance", {"business": business, "request_key": key}, "name", for_update=True
	)
	if existing:
		doc = frappe.get_doc("GYM Attendance", existing, for_update=True)
		doc.check_permission("read")
		if doc.member != member or doc.branch != branch:
			frappe.throw(_("La clave ya fue usada para otra asistencia."))
	else:
		doc = frappe.get_doc(
			{
				"doctype": "GYM Attendance",
				"business": business,
				"branch": branch,
				"member": member,
				"request_key": key,
			}
		).insert()
	return {field: doc.get(field) for field in ("name", "result", "reason", "membership", "recorded_at")}
