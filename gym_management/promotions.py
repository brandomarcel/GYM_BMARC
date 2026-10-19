"""Individual price adjustments; no receipt creation or grouped entitlements."""

import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from gym_management.membership_rules import money
from gym_management.permissions import require_access


def price_quote(plan, promotion=None, discount=0, discount_reason=None, lock=False):
	price = money(plan.price)
	value = money(discount)
	snapshot = None
	if promotion:
		campaign = frappe.get_doc("GYM Promotion", promotion, for_update=lock)
		campaign.check_permission("read")
		if campaign.business != plan.business or campaign.plan != plan.name:
			frappe.throw(
				_("La promoción no corresponde al negocio y plan seleccionados."), frappe.PermissionError
			)
		if campaign.status != "Activo" or not getdate(campaign.valid_from) <= getdate(nowdate()) <= getdate(
			campaign.valid_until
		):
			frappe.throw(_("La promoción no está disponible en la fecha de contratación."))
		value = (
			money(price * money(campaign.benefit_value) / 100)
			if campaign.benefit_type == "Porcentaje"
			else money(campaign.benefit_value)
		)
		if money(discount) not in (money(0), value):
			frappe.throw(_("No se puede acumular un descuento manual con una promoción."))
		discount_reason = _("Promoción: {0}").format(campaign.promotion_name)
		snapshot = {
			field: campaign.get(field)
			for field in (
				"name",
				"promotion_name",
				"plan",
				"valid_from",
				"valid_until",
				"benefit_type",
				"benefit_value",
				"description",
			)
		}
	elif value:
		require_access(plan.business, "gym.memberships.discount")
		if not (discount_reason or "").strip():
			frappe.throw(_("Indique el motivo del descuento."))
	if value < 0 or value > price:
		frappe.throw(_("El descuento debe estar entre cero y el precio."))
	return {
		"price": price,
		"discount": value,
		"discount_reason": discount_reason or "",
		"total": price - value,
		"promotion": promotion or None,
		"conditions": snapshot,
	}


def apply_price(membership, plan):
	previous = membership.get_doc_before_save()
	discount = membership.discount
	if (
		previous
		and membership.promotion
		and previous.promotion == membership.promotion
		and money(discount) == money(previous.discount)
	):
		discount = 0
	quote = price_quote(plan, membership.promotion, discount, membership.discount_reason, lock=True)
	if (
		membership.promotion
		and membership.docstatus == 1
		and previous
		and (
			previous.promotion != membership.promotion
			or money(previous.price) != quote["price"]
			or money(previous.discount) != quote["discount"]
			or (json.loads(previous.promotion_snapshot or "null") or {}).get("conditions")
			!= json.loads(json.dumps(quote["conditions"], default=str))
		)
	):
		frappe.throw(_("La promoción cambió. Guarde y revise el borrador antes de confirmar."))
	for field in ("price", "discount", "discount_reason", "total"):
		membership.set(field, quote[field])
	membership.promotion_snapshot = (
		json.dumps(
			{
				"conditions": quote["conditions"],
				"price": str(quote["price"]),
				"discount": str(quote["discount"]),
				"total": str(quote["total"]),
				"applied_by": frappe.session.user,
				"applied_at": str(now_datetime()),
			},
			default=str,
			sort_keys=True,
		)
		if membership.promotion
		else None
	)
