import frappe
from frappe import _

from gym_management.membership_rules import money
from gym_management.permissions import allowed_businesses, require_access, require_branch, scope_condition


class MembershipSource:
	def authorize(self, receipt, action, user, for_update=False):
		permission = {
			"read": "gym.payments.read",
			"record": "gym.payments.record",
			"cancel": "gym.payments.cancel",
		}[action]
		require_access(receipt.business, permission, user)
		membership = frappe.get_doc("GYM Membership", receipt.source_name, for_update=for_update)
		if membership.business != receipt.business:
			frappe.throw(_("El contrato no pertenece al negocio."), frappe.PermissionError)
		require_branch(receipt.business, membership.origin_branch, user, allow_inactive=action == "read")
		if action == "record" and membership.docstatus != 1:
			frappe.throw(_("El contrato debe estar confirmado para recibir cobros."))
		return membership

	def lock(self, receipt):
		member = frappe.db.get_value("GYM Membership", receipt.source_name, "member")
		frappe.db.get_value("GYM Member", member, "name", for_update=True)
		frappe.db.get_value("GYM Membership", receipt.source_name, "name", for_update=True)
		self.authorize(
			receipt, "record" if receipt.docstatus != 2 else "cancel", frappe.session.user, for_update=True
		)

	def total(self, receipt):
		return money(frappe.db.get_value("GYM Membership", receipt.source_name, "total"))

	def validate_cash_branch(self, receipt, terminal):
		from facturada_core.api.pos_terminal import resolve_pos_terminal_for_invoice

		resolve_pos_terminal_for_invoice(receipt.business, pos_terminal=terminal, user=frappe.session.user)
		membership = frappe.get_doc("GYM Membership", receipt.source_name)
		establishment = frappe.db.get_value("GYM Branch", membership.origin_branch, "establishment")
		terminal_data = frappe.db.get_value(
			"FacturADA POS Terminal", terminal, ["business", "establishment", "status"], as_dict=True
		)
		if (
			not establishment
			or not terminal_data
			or terminal_data.business != receipt.business
			or terminal_data.status != "Activo"
			or terminal_data.establishment != establishment
		):
			frappe.throw(
				_("El terminal de caja no corresponde a la sede del contrato."), frappe.PermissionError
			)

	def receipt_query(self, user):
		businesses = allowed_businesses("gym.payments.read", user)
		if not businesses:
			return "1=0"
		business_sql = ",".join(frappe.db.escape(b) for b in businesses)
		return f"""(`tabFacturADA Payment Receipt`.source_doctype = 'GYM Membership'
		AND `tabFacturADA Payment Receipt`.business IN ({business_sql})
		AND `tabFacturADA Payment Receipt`.source_name IN
		(SELECT name FROM `tabGYM Membership` WHERE {scope_condition('GYM Membership', user)}))"""
