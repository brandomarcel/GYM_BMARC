"""Business and branch boundaries for the new GYM models, including Desk and files."""

import frappe
from facturada_core.api.business import (
	get_allowed_business_names,
	get_business_role,
	has_business_permission,
	require_business_permission,
	validate_business_access,
)
from facturada_core.api.license import enforce_feature, is_feature_enabled
from frappe import _

GYM_DOCTYPES = (
	"GYM Branch",
	"GYM Branch User",
	"GYM Member",
	"GYM Membership Plan",
	"GYM Promotion",
	"GYM Membership",
	"GYM Attendance",
	"GYM Billing Request",
)
FILE_DOCTYPES = (
	*GYM_DOCTYPES,
	"GYM Membership Branch",
	"FacturADA Payment Receipt",
	"FacturADA Lite Invoice",
	"FacturADA Receipt Application",
)
READ_TYPES = {"read", "select", "print"}
PERMISSIONS = {
	"GYM Branch": ("gym.branches.read", "gym.branches.manage"),
	"GYM Branch User": ("gym.branches.read", "gym.users.manage"),
	"GYM Member": ("gym.members.read", "gym.members.manage"),
	"GYM Membership Plan": ("gym.plans.read", "gym.plans.manage"),
	"GYM Promotion": ("gym.plans.read", "gym.plans.manage"),
	"GYM Membership": ("gym.memberships.read", "gym.memberships.manage"),
	"GYM Attendance": ("gym.attendance.read", "gym.attendance.record"),
	"GYM Billing Request": ("gym.memberships.read", "gym.memberships.read"),
}
BRANCH_FIELDS = {
	"GYM Branch": "name",
	"GYM Branch User": "branch",
	"GYM Member": "home_branch",
	"GYM Membership": "origin_branch",
	"GYM Attendance": "branch",
	"GYM Billing Request": "origin_branch",
}


def deny():
	frappe.throw(_("No tiene acceso a esta operación de gimnasio."), frappe.PermissionError)


def require_access(business, permission, user=None):
	user = user or frappe.session.user
	if user == "Guest" or not frappe.db.get_value("User", user, "enabled"):
		deny()
	validate_business_access(business, user=user)
	enforce_feature("gym", business=business)
	require_business_permission(business, permission, user=user)


def is_business_admin(business, user=None):
	return get_business_role(business, user=user) == "Administrador"


def require_branch(business, branch, user=None, allow_inactive=False):
	user = user or frappe.session.user
	row = frappe.db.get_value("GYM Branch", branch, ["business", "status"], as_dict=True)
	if not row or row.business != business:
		deny()
	if is_business_admin(business, user):
		if allow_inactive or row.status == "Activo":
			return
	elif row.status == "Activo" and frappe.db.exists(
		"GYM Branch User", {"business": business, "branch": branch, "user": user, "status": "Activo"}
	):
		return
	deny()


def check_document(doc, ptype="read", user=None):
	user = user or frappe.session.user
	if ptype in READ_TYPES:
		permission = PERMISSIONS[doc.doctype][0]
	elif doc.doctype == "GYM Membership" and ptype == "cancel":
		permission = "gym.memberships.cancel"
	elif ptype in {"write", "create", "delete", "submit"}:
		if doc.doctype == "GYM Attendance" and ptype != "create":
			deny()
		permission = PERMISSIONS[doc.doctype][1]
	else:
		deny()
	require_access(doc.business, permission, user)
	if doc.doctype == "GYM Billing Request":
		require_business_permission(
			doc.business, "billing.read" if ptype in READ_TYPES else "billing.create", user=user
		)
		require_branch(doc.business, doc.origin_branch, user, allow_inactive=ptype in READ_TYPES)
		return
	if doc.doctype in {"GYM Membership Plan", "GYM Promotion"}:
		return
	if doc.doctype == "GYM Branch User":
		# Personnel assignments are visible to their subject or the business administrator.
		if not is_business_admin(doc.business, user):
			if ptype not in READ_TYPES or doc.user != user:
				deny()
		require_branch(doc.business, doc.branch, user, allow_inactive=True)
	elif doc.doctype == "GYM Member":
		require_branch(doc.business, doc.home_branch, user, allow_inactive=ptype in READ_TYPES)
	elif doc.doctype in {"GYM Membership", "GYM Attendance"}:
		require_branch(
			doc.business, doc.get(BRANCH_FIELDS[doc.doctype]), user, allow_inactive=ptype in READ_TYPES
		)
	elif not doc.is_new():
		require_branch(doc.business, doc.name, user, allow_inactive=True)


def has_permission(doc, ptype=None, user=None, **kwargs):
	try:
		check_document(doc, ptype or "read", user)
	except (frappe.PermissionError, frappe.ValidationError):
		return False
	return True


def allowed_businesses(permission, user):
	if user == "Guest" or not frappe.db.get_value("User", user, "enabled"):
		return []
	return [
		business
		for business in get_allowed_business_names(user)
		if has_business_permission(business, permission, user=user)
		and is_feature_enabled("gym", business=business)
	]


def scope_condition(doctype, user=None):
	"""SQL identifiers are constants; every variable value is escaped by the DB driver."""
	user = user or frappe.session.user
	permission = PERMISSIONS[doctype][0]
	businesses = allowed_businesses(permission, user)
	if doctype == "GYM Billing Request":
		businesses = [b for b in businesses if has_business_permission(b, "billing.read", user=user)]
	if not businesses:
		return "1=0"
	table = f"`tab{doctype}`"
	clauses = []
	for business in businesses:
		base = f"{table}.business = {frappe.db.escape(business)}"
		if not is_business_admin(business, user) and doctype in BRANCH_FIELDS:
			branch_field = BRANCH_FIELDS[doctype]
			base += f""" AND {table}.`{branch_field}` IN (
				SELECT branch.name FROM `tabGYM Branch` branch
				INNER JOIN `tabGYM Branch User` assignment ON assignment.branch = branch.name
				AND assignment.business = branch.business
				WHERE branch.business = {frappe.db.escape(business)} AND branch.status = 'Activo'
				AND assignment.user = {frappe.db.escape(user)} AND assignment.status = 'Activo')"""
			if doctype == "GYM Branch User":
				base += f" AND {table}.user = {frappe.db.escape(user)}"
		clauses.append(f"({base})")
	return "(" + " OR ".join(clauses) + ")"


def branch_query(user=None):
	return scope_condition("GYM Branch", user)


def assignment_query(user=None):
	return scope_condition("GYM Branch User", user)


def member_query(user=None):
	return scope_condition("GYM Member", user)


def plan_query(user=None):
	return scope_condition("GYM Membership Plan", user)


def membership_query(user=None):
	return scope_condition("GYM Membership", user)


def attendance_query(user=None):
	return scope_condition("GYM Attendance", user)


def billing_request_query(user=None):
	return scope_condition("GYM Billing Request", user)


def billing_invoice_permission(doc, ptype=None, user=None, **kwargs):
	if doc.source_doctype != "GYM Billing Request":
		return None
	return has_permission(frappe.get_doc("GYM Billing Request", doc.source_name), ptype or "read", user)


def billing_invoice_query(user=None):
	return f"""(source_doctype IS NULL OR source_doctype != 'GYM Billing Request'
	OR source_name IN (SELECT name FROM `tabGYM Billing Request`
	WHERE {scope_condition('GYM Billing Request', user)}))"""


def invoice_request(name):
	"""Only GYM fiscal sources extend the other apps' file/share policies."""
	return frappe.db.get_value(
		"FacturADA Lite Invoice", {"name": name, "source_doctype": "GYM Billing Request"}, "source_name"
	)


def file_permission(doc, ptype=None, user=None, **kwargs):
	if doc.attached_to_doctype not in FILE_DOCTYPES:
		return None  # Leave all other apps' file policies unchanged.
	if not doc.attached_to_name or not frappe.db.exists(doc.attached_to_doctype, doc.attached_to_name):
		return False
	parent = frappe.get_doc(doc.attached_to_doctype, doc.attached_to_name)
	if parent.doctype == "FacturADA Lite Invoice":
		request = invoice_request(parent.name)
		if not request:
			return None
		parent = frappe.get_doc("GYM Billing Request", request)
	if parent.doctype == "GYM Membership Branch":
		if parent.parenttype not in {"GYM Membership Plan", "GYM Membership"}:
			return False
		parent = frappe.get_doc(parent.parenttype, parent.parent)
	if parent.doctype == "FacturADA Payment Receipt":
		from facturada_lite.api.receipts import has_permission as receipt_permission

		return receipt_permission(parent, "read" if ptype in READ_TYPES else "write", user)
	if parent.doctype == "FacturADA Receipt Application":
		from facturada_lite.payments.applications import has_permission as application_permission

		return application_permission(parent, "read" if ptype in READ_TYPES else "write", user)
	return has_permission(parent, "read" if ptype in READ_TYPES else "write", user)


def file_query(user=None):
	if not frappe.db.exists("DocType", "GYM Branch"):
		return ""  # Existing sites remain compatible until the new schemas are migrated.
	options = []
	for doctype in FILE_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		if doctype == "FacturADA Lite Invoice":
			condition = f"""(source_doctype IS NULL OR source_doctype != 'GYM Billing Request'
			OR source_name IN (SELECT name FROM `tabGYM Billing Request`
			WHERE {scope_condition('GYM Billing Request', user)}))"""
		elif doctype == "FacturADA Receipt Application":
			from facturada_lite.payments.applications import query_condition

			condition = query_condition(user)
		elif doctype == "FacturADA Payment Receipt":
			from facturada_lite.api.receipts import query_condition

			condition = query_condition(user)
		elif doctype == "GYM Membership Branch":
			parts = []
			for parent_type in ("GYM Membership Plan", "GYM Membership"):
				parts.append(f"""(`tabGYM Membership Branch`.parenttype = {frappe.db.escape(parent_type)}
				AND `tabGYM Membership Branch`.parent IN
				(SELECT name FROM `tab{parent_type}` WHERE {scope_condition(parent_type, user)}))""")
			condition = "(" + " OR ".join(parts) + ")"
		else:
			condition = scope_condition(doctype, user)
		options.append(
			f"""(`tabFile`.attached_to_doctype = {frappe.db.escape(doctype)}
			AND `tabFile`.attached_to_name IN
			(SELECT name FROM `tab{doctype}` WHERE {condition}))"""
		)
	names = ",".join(frappe.db.escape(dt) for dt in FILE_DOCTYPES)
	return f"(`tabFile`.attached_to_doctype IS NULL OR `tabFile`.attached_to_doctype NOT IN ({names}) OR {' OR '.join(options)})"


def validate_file(doc, method=None):
	# Do not let a user create an unscoped alias to a known private GYM URL.
	if doc.file_url:
		for reference in frappe.get_all(
			"File",
			filters={"file_url": doc.file_url, "attached_to_doctype": ["in", FILE_DOCTYPES]},
			fields=["name", "attached_to_doctype", "attached_to_name"],
		):
			if reference.name != doc.name and file_permission(reference, "read") is False:
				deny()
	previous = doc.get_doc_before_save()
	if previous and previous.attached_to_doctype in FILE_DOCTYPES:
		if file_permission(previous, "read") is not None and (
			doc.attached_to_doctype,
			doc.attached_to_name,
		) != (
			previous.attached_to_doctype,
			previous.attached_to_name,
		):
			deny()  # Never detach/reparent an existing GYM file to bypass its original boundary.
	if doc.attached_to_doctype in FILE_DOCTYPES:
		if file_permission(doc, "write") is None:
			return
		if (
			not doc.is_private
			or (doc.file_url and not doc.file_url.startswith("/private/files/"))
			or not file_permission(doc, "write")
		):
			deny()


def prevent_sharing(doc, method=None):
	if doc.share_doctype == "FacturADA Lite Invoice" and not invoice_request(doc.share_name):
		return
	if doc.share_doctype in FILE_DOCTYPES:
		deny()
	if doc.share_doctype == "File":
		file = frappe.get_doc("File", doc.share_name)
		if file.attached_to_doctype in FILE_DOCTYPES and file_permission(file, "read") is not None:
			deny()


def promotion_query(user=None):
	return scope_condition("GYM Promotion", user)
