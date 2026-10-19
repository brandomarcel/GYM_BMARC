"""Promotion discovery and pricing for Desk and future Angular consumers."""

import frappe
from frappe import _
from frappe.utils import nowdate

from gym_management.permissions import require_access, require_branch
from gym_management.promotions import price_quote


def authorized_plan(business, plan, origin_branch):
	require_access(business, "gym.memberships.manage")
	require_branch(business, origin_branch)
	doc = frappe.get_doc("GYM Membership Plan", plan)
	doc.check_permission("read")
	if doc.business != business or doc.status != "Activo":
		frappe.throw(_("El plan no está disponible para este negocio."), frappe.PermissionError)
	return doc


@frappe.whitelist(methods=["GET", "POST"])
def list_promotions(business, plan, origin_branch):
	authorized_plan(business, plan, origin_branch)
	return frappe.get_list(
		"GYM Promotion",
		filters={
			"business": business,
			"plan": plan,
			"status": "Activo",
			"valid_from": ["<=", nowdate()],
			"valid_until": [">=", nowdate()],
		},
		fields=["name", "promotion_name", "benefit_type", "benefit_value", "valid_from", "valid_until"],
		order_by="valid_until asc, name asc",
		limit_page_length=100,
	)


@frappe.whitelist(methods=["GET", "POST"])
def quote_price(business, plan, origin_branch, promotion=None, discount=0, discount_reason=None):
	doc = authorized_plan(business, plan, origin_branch)
	return price_quote(doc, promotion, discount, discount_reason)
