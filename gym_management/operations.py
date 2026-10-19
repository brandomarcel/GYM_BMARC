"""Read models for the Angular reception UI; authorization stays on the server."""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from gym_management.permissions import require_access, require_branch, scope_condition


def date_range(from_date, to_date):
	try:
		start, end = getdate(from_date), getdate(to_date)
	except (ValueError, TypeError, OverflowError):
		frappe.throw(_("Indique fechas válidas."))
	if not from_date or not to_date or start > end or (end - start).days > 365:
		frappe.throw(_("Seleccione un período de hasta 366 días con inicio anterior o igual al fin."))
	return start, end


def attendance_history(business, from_date, to_date, branch=None, result=None, page=1, page_size=50):
	require_access(business, "gym.attendance.read")
	if branch:
		require_branch(business, branch, allow_inactive=True)
	start, end = date_range(from_date, to_date)
	page, size = cint(page), cint(page_size)
	if not 1 <= page <= 10000 or size not in {25, 50, 100, 200}:
		frappe.throw(_("Use página desde 1 hasta 10000 y tamaño 25, 50, 100 o 200."))
	if result not in (None, "", "Permitido", "Denegado"):
		frappe.throw(_("Resultado de acceso no válido."))
	condition = scope_condition("GYM Attendance")
	params = {"business": business, "start": start, "until": end + timedelta(days=1)}
	condition += " AND `tabGYM Attendance`.business = %(business)s"
	condition += " AND recorded_at >= %(start)s AND recorded_at < %(until)s"
	if branch:
		condition += " AND `tabGYM Attendance`.branch = %(branch)s"
		params["branch"] = branch
	if result:
		condition += " AND result = %(result)s"
		params["result"] = result
	totals = frappe.db.sql(
		f"""SELECT COUNT(*) AS records, COALESCE(SUM(result = 'Permitido'), 0) AS allowed,
		COALESCE(SUM(result = 'Denegado'), 0) AS denied FROM `tabGYM Attendance` WHERE {condition}""",
		params,
		as_dict=True,
	)[0]
	# Attendance can refer to a visitor from another home branch. Do not disclose
	# their full profile name simply because this operator may read the visit.
	member_scope = scope_condition("GYM Member")
	rows = frappe.db.sql(
		f"""SELECT `tabGYM Attendance`.name, `tabGYM Attendance`.branch,
		`tabGYM Attendance`.member, `tabGYM Member`.full_name AS member_name,
		`tabGYM Attendance`.membership, recorded_at, result, reason, recorded_by
		FROM `tabGYM Attendance` LEFT JOIN `tabGYM Member`
		ON `tabGYM Member`.name = `tabGYM Attendance`.member
		AND `tabGYM Member`.business = `tabGYM Attendance`.business AND {member_scope}
		WHERE {condition} ORDER BY recorded_at DESC, `tabGYM Attendance`.name DESC
		LIMIT %(limit)s OFFSET %(offset)s""",
		{**params, "limit": size, "offset": (page - 1) * size},
		as_dict=True,
	)
	return {
		"data": rows,
		"totals": {key: int(value) for key, value in totals.items()},
		"pagination": {
			"page": page,
			"page_size": size,
			"total": totals.records,
			"has_next": page * size < totals.records,
		},
		"filters": {
			"business": business,
			"branch": branch or None,
			"from_date": start,
			"to_date": end,
			"result": result or None,
		},
	}


def reception_panel(business, branch=None, horizon_days=7):
	for permission in ("gym.memberships.read", "gym.payments.read", "gym.attendance.read"):
		require_access(business, permission)
	if branch:
		require_branch(business, branch, allow_inactive=True)
	days = cint(horizon_days)
	if not 1 <= days <= 90:
		frappe.throw(_("El horizonte de vencimientos debe estar entre 1 y 90 días."))
	today = getdate(nowdate())
	until = today + timedelta(days=days)
	params = {"business": business, "today": today, "until": until}
	condition = scope_condition("GYM Membership")
	condition += " AND `tabGYM Membership`.business = %(business)s AND `tabGYM Membership`.docstatus = 1"
	if branch:
		condition += " AND `tabGYM Membership`.origin_branch = %(branch)s"
		params["branch"] = branch
	payments_available = "facturada_lite" in frappe.get_installed_apps()
	if payments_available:
		join = """LEFT JOIN (SELECT source_name, SUM(amount) AS paid
		FROM `tabFacturADA Payment Receipt` WHERE business = %(business)s
		AND source_doctype = 'GYM Membership' AND docstatus = 1 GROUP BY source_name) receipts
		ON receipts.source_name = `tabGYM Membership`.name"""
		paid = "COALESCE(receipts.paid, 0)"
	else:
		join, paid = "", "0"
	balance = f"GREATEST(`tabGYM Membership`.total - {paid}, 0)"
	criteria = {
		"active_contracts": "start_date <= %(today)s AND end_date >= %(today)s",
		"expiring_contracts": "end_date BETWEEN %(today)s AND %(until)s",
		"expired_contracts": "end_date < %(today)s",
		"contracts_with_balance": f"{balance} > 0",
	}
	aggregates = ", ".join(f"COALESCE(SUM({predicate}), 0) AS {key}" for key, predicate in criteria.items())
	cards = frappe.db.sql(
		f"""SELECT {aggregates}, COALESCE(SUM({balance}), 0) AS outstanding
		FROM `tabGYM Membership` {join} WHERE {condition}""",
		params,
		as_dict=True,
	)[0]
	member_scope = scope_condition("GYM Member")
	lists = {}
	for label, key, order in (
		("expiring", "expiring_contracts", "end_date ASC"),
		("expired", "expired_contracts", "end_date DESC"),
		("with_balance", "contracts_with_balance", "outstanding DESC"),
	):
		lists[label] = frappe.db.sql(
			f"""SELECT `tabGYM Membership`.name, `tabGYM Membership`.member,
			`tabGYM Member`.full_name AS member_name, origin_branch, start_date, end_date,
			`tabGYM Membership`.total, {paid} AS paid, {balance} AS outstanding
			FROM `tabGYM Membership` {join} LEFT JOIN `tabGYM Member`
			ON `tabGYM Member`.name = `tabGYM Membership`.member
			AND `tabGYM Member`.business = `tabGYM Membership`.business AND {member_scope}
			WHERE {condition} AND {criteria[key]}
			ORDER BY {order}, `tabGYM Membership`.name ASC LIMIT 10""",
			params,
			as_dict=True,
		)
	attendance = attendance_history(business, today, today, branch, page_size=25)
	cards.update(entries_today=attendance["totals"]["allowed"], denials_today=attendance["totals"]["denied"])
	lists["recent_attendance"] = attendance["data"][:10]
	return {
		"business": business,
		"branch": branch or None,
		"today": today,
		"until": until,
		"horizon_days": days,
		"currency": "USD",
		"payments_available": payments_available,
		"cards": cards,
		"lists": lists,
		"list_limit": 10,
	}
