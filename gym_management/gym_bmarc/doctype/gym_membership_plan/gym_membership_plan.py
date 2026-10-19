import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr

from gym_management.membership_rules import validate_branches, validate_policies
from gym_management.permissions import check_document


class GYMMembershipPlan(Document):
	def validate(self):
		check_document(self, "create" if self.is_new() else "write")
		previous = self.get_doc_before_save()
		if previous and previous.business != self.business:
			frappe.throw(_("No puede cambiar el negocio del plan."), frappe.PermissionError)
		self.plan_code = cstr(self.plan_code).strip().upper()
		self.plan_name = cstr(self.plan_name).strip()
		if not self.plan_code or not self.plan_name:
			frappe.throw(_("Indique código y nombre del plan."))
		validate_policies(self)
		validate_branches(self)

	def on_trash(self):
		check_document(self, "delete")
