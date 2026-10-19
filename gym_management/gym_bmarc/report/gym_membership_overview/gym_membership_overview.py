import frappe

from gym_management.permissions import require_access, require_branch, scope_condition


def execute(filters=None):
	filters = frappe._dict(filters or {})
	require_access(filters.business, "gym.reports.view")
	condition = scope_condition("GYM Membership")
	params = {"business": filters.business}
	if filters.branch:
		require_branch(filters.business, filters.branch)
		condition += " AND `tabGYM Membership`.origin_branch = %(branch)s"
		params["branch"] = filters.branch
	if frappe.db.exists("DocType", "FacturADA Payment Receipt"):
		join = """LEFT JOIN (SELECT business, source_name, SUM(amount) AS paid
			FROM `tabFacturADA Payment Receipt` WHERE source_doctype = 'GYM Membership' AND docstatus = 1
			GROUP BY business, source_name) receipts ON receipts.business = `tabGYM Membership`.business
			AND receipts.source_name = `tabGYM Membership`.name"""
		paid = "COALESCE(receipts.paid, 0)"
	else:
		join, paid = "", "0"
	rows = frappe.db.sql(
		f"""SELECT `tabGYM Membership`.name, `tabGYM Membership`.member,
		`tabGYM Membership`.origin_branch, `tabGYM Membership`.start_date, `tabGYM Membership`.end_date,
		`tabGYM Membership`.total, {paid} AS paid, `tabGYM Membership`.total - {paid} AS outstanding
		FROM `tabGYM Membership` {join}
		WHERE `tabGYM Membership`.business = %(business)s AND `tabGYM Membership`.docstatus = 1
		AND {condition} ORDER BY `tabGYM Membership`.end_date ASC""",
		params,
		as_dict=True,
	)
	columns = [
		{
			"fieldname": "name",
			"label": "Membresía",
			"fieldtype": "Link",
			"options": "GYM Membership",
			"width": 140,
		},
		{"fieldname": "member", "label": "Socio", "fieldtype": "Link", "options": "GYM Member", "width": 140},
		{
			"fieldname": "origin_branch",
			"label": "Sucursal",
			"fieldtype": "Link",
			"options": "GYM Branch",
			"width": 140,
		},
		{"fieldname": "start_date", "label": "Inicio", "fieldtype": "Date", "width": 120},
		{"fieldname": "end_date", "label": "Vence", "fieldtype": "Date", "width": 120},
		*[
			{"fieldname": name, "label": label, "fieldtype": "Currency", "options": "USD", "width": 130}
			for name, label in (("total", "Contratado"), ("paid", "Cobrado"), ("outstanding", "Pendiente"))
		],
	]
	return columns, rows
