import frappe
from frappe import _
from frappe.utils import cint

from gym_management.permissions import allowed_businesses, require_access


@frappe.whitelist(methods=["GET", "POST"])
def get_context():
	businesses = allowed_businesses("gym.branches.read", frappe.session.user)
	return {
		"businesses": frappe.get_all(
			"FacturADA Business", filters={"name": ["in", businesses]}, fields=["name", "business_name"]
		)
		if businesses
		else [],
		"branches": frappe.get_list(
			"GYM Branch", fields=["name", "business", "branch_name", "status"], limit_page_length=200
		),
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def business_query(doctype, txt, searchfield, start, page_len, filters):
	if doctype != "FacturADA Business":
		frappe.throw(_("Tipo de búsqueda no permitido."), frappe.PermissionError)
	names = allowed_businesses("gym.branches.read", frappe.session.user)
	if not names:
		return []
	return frappe.get_all(
		"FacturADA Business",
		filters={"name": ["in", names], "business_name": ["like", f"%{txt}%"]},
		fields=["name", "business_name"],
		as_list=True,
		limit_start=max(cint(start), 0),
		limit_page_length=min(max(cint(page_len), 1), 50),
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def business_link_query(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe._dict(filters or {})
	business = filters.get("business")
	require_access(business, "gym.users.manage" if doctype == "User" else "gym.branches.manage")
	if doctype == "User":
		names = frappe.get_all(
			"FacturADA Business User", filters={"business": business, "status": "Activo"}, pluck="user"
		)
		return (
			frappe.get_all(
				"User",
				filters={"name": ["in", names], "enabled": 1},
				or_filters={"name": ["like", f"%{txt}%"], "full_name": ["like", f"%{txt}%"]},
				fields=["name", "full_name"],
				as_list=True,
				limit_start=max(cint(start), 0),
				limit_page_length=min(max(cint(page_len), 1), 50),
			)
			if names
			else []
		)
	if doctype == "FacturADA Establishment":
		return frappe.get_all(
			doctype,
			filters={"business": business, "establishment_name": ["like", f"%{txt}%"]},
			fields=["name", "establishment_name"],
			as_list=True,
			limit_start=max(cint(start), 0),
			limit_page_length=min(max(cint(page_len), 1), 50),
		)
	frappe.throw(_("Tipo de búsqueda no permitido."), frappe.PermissionError)
