import frappe
from facturada_core.api.business_permissions import permissions_for_role
from facturada_core.api.license import is_feature_enabled


def ensure_role():
	if not frappe.db.exists("Role", "GYM User"):
		frappe.get_doc({"doctype": "Role", "role_name": "GYM User", "desk_access": 1}).insert()


def setup():
	ensure_role()
	for doctype, fields in (
		("GYM Branch", ["business", "branch_code"]),
		("GYM Branch User", ["business", "branch", "user"]),
		("GYM Member", ["business", "member_code"]),
		("GYM Membership Plan", ["business", "plan_code"]),
		("GYM Membership", ["business", "request_key"]),
		("GYM Attendance", ["business", "request_key"]),
		("GYM Billing Request", ["business", "request_key"]),
	):
		frappe.db.add_unique(doctype, fields)
	for assignment in frappe.get_all(
		"FacturADA Business User",
		filters={"status": "Activo"},
		fields=["user", "business", "business_role", "status"],
	):
		sync_assignment_user(assignment)


def sync_assignment_user(doc, method=None):
	"""The technical Desk role is only a base; every action checks live Core policy."""
	if not frappe.db.exists("Role", "GYM User"):
		return
	if doc.status != "Activo" or doc.user in {"Guest", "Administrator"}:
		return
	if not is_feature_enabled("gym", business=doc.business):
		return
	permissions = permissions_for_role(doc.business_role)
	if "*" in permissions or any(p.startswith("gym.") for p in permissions):
		user = frappe.get_doc("User", doc.user)
		roles = ["GYM User"]
		if frappe.db.exists("Role", "FacturADA Payments User"):
			roles.append("FacturADA Payments User")
		missing = set(roles) - {row.role for row in user.roles}
		if user.enabled and missing:
			# Only this derived technical role is added by a trusted assignment event.
			# It never grants access without live business/feature/branch checks.
			user.append_roles(*sorted(missing))
			user.save(ignore_permissions=True)


def sync_business_users(doc, method=None):
	for assignment in frappe.get_all(
		"FacturADA Business User",
		filters={"business": doc.business, "status": "Activo"},
		fields=["user", "business", "business_role", "status"],
	):
		sync_assignment_user(assignment)


def after_app_install(app_name):
	if app_name == "facturada_lite":
		for assignment in frappe.get_all(
			"FacturADA Business User",
			filters={"status": "Activo"},
			fields=["user", "business", "business_role", "status"],
		):
			sync_assignment_user(assignment)
