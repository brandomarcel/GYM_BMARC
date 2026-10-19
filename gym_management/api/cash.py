"""Authenticated transport for the scoped shared-cash adapter."""

import frappe

from gym_management import cash


@frappe.whitelist(methods=["GET", "POST"])
def get_cash_context(business, branch, user=None):
	return cash.get_cash_context(business, branch, user)


@frappe.whitelist(methods=["GET", "POST"])
def get_cash_summary(business, branch, cash_opening, user=None):
	return cash.get_cash_summary(business, branch, cash_opening, user)


@frappe.whitelist(methods=["POST"])
def open_cash(business, branch, pos_terminal, opening_amount, user=None, notes=None):
	return cash.open_cash(business, branch, pos_terminal, opening_amount, user, notes)


@frappe.whitelist(methods=["POST"])
def close_cash(business, branch, cash_opening, cash_counted, user=None, notes=None):
	return cash.close_cash(business, branch, cash_opening, cash_counted, user, notes)
