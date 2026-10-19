import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate

POLICY_FIELDS = (
	"duration",
	"duration_unit",
	"price",
	"currency",
	"access_mode",
	"renewal_mode",
	"payment_policy",
	"minimum_percentage",
	"grace_days",
)
REQUEST_FIELDS = (
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


def request_hash(data):
	fields = {key: data.get(key) or None for key in REQUEST_FIELDS}
	fields["discount"] = str(money(data.get("discount")))
	if not fields.get("promotion"):
		fields.pop("promotion", None)
	return hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()


def money(value):
	try:
		amount = Decimal(str(value or 0))
		if not amount.is_finite():
			raise ValueError
		return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
	except (ValueError, InvalidOperation):
		frappe.throw(_("Importe no válido."))


def validate_policies(doc):
	for field in ("duration", "grace_days"):
		try:
			value = Decimal(str(doc.get(field) or 0))
		except InvalidOperation:
			frappe.throw(_("La duración y los días de gracia deben ser enteros válidos."))
		if (
			not value.is_finite()
			or value != value.to_integral_value()
			or value < (1 if field == "duration" else 0)
		):
			frappe.throw(_("La duración y los días de gracia deben ser enteros válidos."))
	doc.price = money(doc.price)
	if doc.price < 0:
		frappe.throw(_("El precio no puede ser negativo."))
	minimum = money(doc.minimum_percentage)
	if minimum < 0 or minimum > 100:
		frappe.throw(_("El porcentaje mínimo debe estar entre 0 y 100."))
	if doc.payment_policy == "Abonos" and doc.price > 0 and minimum <= 0:
		frappe.throw(_("El acceso con abonos requiere un porcentaje mínimo mayor a cero."))
	if doc.currency != "USD":
		frappe.throw(_("Esta versión de GYM opera en USD."))


def end_date(start, duration, unit):
	boundary = (
		add_days(getdate(start), cint(duration))
		if unit == "Dias"
		else add_months(getdate(start), cint(duration))
	)
	return getdate(add_days(boundary, -1))


def validate_branches(doc):
	names = [row.branch for row in doc.branches]
	if len(names) != len(set(names)):
		frappe.throw(_("No puede repetir una sede."))
	if doc.access_mode == "Varias sedes":
		if not names:
			frappe.throw(_("Seleccione las sedes incluidas."))
	else:
		doc.set("branches", [])
	for name in names if doc.access_mode == "Varias sedes" else []:
		if not frappe.db.exists("GYM Branch", {"name": name, "business": doc.business, "status": "Activo"}):
			frappe.throw(_("Una sede no está activa o no pertenece al negocio."), frappe.PermissionError)
