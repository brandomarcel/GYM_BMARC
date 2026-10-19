"""Authenticated, read-only contracts for the independent Angular GYM frontend."""

import frappe

from gym_management.operations import attendance_history, reception_panel


@frappe.whitelist(methods=["GET", "POST"])
def get_reception_panel(business, branch=None, horizon_days=7):
	return reception_panel(business, branch, horizon_days)


@frappe.whitelist(methods=["GET", "POST"])
def list_attendance(business, from_date, to_date, branch=None, result=None, page=1, page_size=50):
	return attendance_history(business, from_date, to_date, branch, result, page, page_size)
