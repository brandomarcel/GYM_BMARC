"""Scoped Desk adapter. Restaurante remains the owner of cash transactions."""

import frappe
from facturada_core.api.business import has_business_permission, require_business_permission
from facturada_core.api.license import enforce_feature
from facturada_core.api.pos_terminal import list_pos_terminals, resolve_pos_terminal_for_invoice
from frappe import _

from gym_management.membership_rules import money
from gym_management.permissions import require_access, require_branch

OPENING = "FacturADA Restaurant Cash Opening"


def authorize(business, branch, user=None, manage=False):
	require_access(business, "gym.payments.read")
	require_branch(business, branch)
	if "facturada_restaurante" not in frappe.get_installed_apps():
		frappe.throw(_("Instale Restaurante para utilizar la caja compartida."))
	enforce_feature("pos", business=business)
	user = user or frappe.session.user
	if manage or user != frappe.session.user:
		require_business_permission(business, "restaurant.cash.manage")
	require_access(business, "gym.payments.record", user=user)
	require_branch(business, branch, user=user)
	return user


def terminals_for(business, branch, user):
	establishment = frappe.db.get_value("GYM Branch", branch, "establishment")
	if not establishment:
		return []
	return [
		{"name": row["name"], "terminal_name": row["terminal_name"]}
		for row in list_pos_terminals(business=business, user=user)["data"]
		if row["establishment"] == establishment
	]


def get_cash_context(business, branch, user=None):
	user = authorize(business, branch, user)
	terminals = terminals_for(business, branch, user)
	names = [row["name"] for row in terminals]
	opening = (
		frappe.db.get_value(
			OPENING,
			{"business": business, "user": user, "status": "Abierta", "pos_terminal": ["in", names]},
			["name", "pos_terminal", "opened_at", "opening_amount", "user"],
			as_dict=True,
		)
		if names
		else None
	)
	can_manage = has_business_permission(business, "restaurant.cash.manage")
	users = []
	if can_manage:
		for row in frappe.get_all(
			"FacturADA Business User", filters={"business": business, "status": "Activo"}, fields=["user"]
		):
			try:
				require_access(business, "gym.payments.record", user=row.user)
				require_branch(business, branch, user=row.user)
			except (frappe.PermissionError, frappe.ValidationError):
				continue
			users.append({"name": row.user, "full_name": frappe.db.get_value("User", row.user, "full_name")})
	if not any(row["name"] == user for row in users):
		users.insert(0, {"name": user, "full_name": frappe.db.get_value("User", user, "full_name")})
	return {
		"opening": opening,
		"terminals": terminals,
		"users": users,
		"user": user,
		"can_manage": can_manage,
	}


def get_cash_summary(business, branch, cash_opening, user=None):
	user = authorize(business, branch, user, manage=True)
	from facturada_restaurante.api.frontend import get_cash_payment_totals, get_withdrawals_total

	opening = scoped_opening(business, branch, user, cash_opening)
	payments = get_cash_payment_totals(opening)
	withdrawals = money(get_withdrawals_total(opening))
	cash = sum((money(row.amount) for row in payments if row.payment_code == "01"), money(0))
	return {
		"opening_amount": money(opening.opening_amount),
		"payments": payments,
		"withdrawals": withdrawals,
		"cash_system": money(opening.opening_amount) + cash - withdrawals,
	}


def scoped_opening(business, branch, user, name, for_update=False):
	opening = frappe.get_doc(OPENING, name, for_update=for_update)
	if opening.business != business or opening.user != user:
		frappe.throw(
			_("La apertura no corresponde al negocio y cajero seleccionados."), frappe.PermissionError
		)
	terminal = resolve_pos_terminal_for_invoice(business, pos_terminal=opening.pos_terminal, user=user)
	if not terminal or terminal.establishment != frappe.db.get_value("GYM Branch", branch, "establishment"):
		frappe.throw(_("La caja no corresponde a esta sucursal."), frappe.PermissionError)
	if opening.status != "Abierta":
		frappe.throw(_("La caja ya está cerrada. Actualice la pantalla."))
	return opening


def nonnegative(value):
	if value is None or value == "":
		frappe.throw(_("Indique el importe, incluso cuando sea cero."))
	amount = money(value)
	if amount < 0:
		frappe.throw(_("El importe no puede ser negativo."))
	return amount


def open_cash(business, branch, pos_terminal, opening_amount, user=None, notes=None):
	user = authorize(business, branch, user, manage=True)
	amount = nonnegative(opening_amount)
	if not pos_terminal:
		frappe.throw(_("Seleccione el terminal de esta sucursal."), frappe.PermissionError)
	terminal = resolve_pos_terminal_for_invoice(business, pos_terminal=pos_terminal, user=user)
	if not terminal or terminal.establishment != frappe.db.get_value("GYM Branch", branch, "establishment"):
		frappe.throw(_("Seleccione un terminal de esta sucursal."), frappe.PermissionError)
	# Serialize attempts for this cashier before delegating to the existing engine.
	frappe.db.get_value("User", user, "name", for_update=True)
	if frappe.db.get_value(
		OPENING, {"business": business, "user": user, "status": "Abierta"}, "name", for_update=True
	):
		frappe.throw(_("Este cajero ya tiene una caja abierta. Actualice antes de continuar."))
	from facturada_restaurante.api.frontend import open_cash_register

	return open_cash_register(
		{
			"business": business,
			"user": user,
			"pos_terminal": pos_terminal,
			"opening_amount": float(amount),
			"notes": notes,
		}
	)["data"]


def close_cash(business, branch, cash_opening, cash_counted, user=None, notes=None):
	user = authorize(business, branch, user, manage=True)
	amount = nonnegative(cash_counted)
	frappe.db.get_value(OPENING, cash_opening, "name", for_update=True)
	scoped_opening(business, branch, user, cash_opening, for_update=True)
	from facturada_restaurante.api.frontend import close_cash_register

	return close_cash_register(
		{
			"business": business,
			"user": user,
			"cash_opening": cash_opening,
			"cash_counted": float(amount),
			"notes": notes,
		}
	)["data"]
