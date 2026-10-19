import frappe
from frappe import _
from frappe.model.document import Document

from gym_management.billing.service import persist_draft, prepare_document


class GYMBillingRequest(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(
				_("La solicitud fiscal es inmutable. Conserve su historial."), frappe.PermissionError
			)
		prepare_document(self)

	def after_insert(self):
		persist_draft(self)

	def on_trash(self):
		frappe.throw(_("No se permite borrar el historial de solicitudes fiscales."), frappe.PermissionError)
