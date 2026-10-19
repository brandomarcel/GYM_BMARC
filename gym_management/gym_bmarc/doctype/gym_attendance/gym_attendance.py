import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from gym_management.permissions import check_document


class GYMAttendance(Document):
	def validate(self):
		check_document(self, "create" if self.is_new() else "write")
		if not self.is_new():
			frappe.throw(_("Las asistencias son registros inmutables."))
		if not frappe.db.exists("GYM Member", {"name": self.member, "business": self.business}):
			frappe.throw(_("El socio no pertenece al negocio."), frappe.PermissionError)
		from gym_management.api.memberships import evaluate_access

		frappe.db.get_value("GYM Member", self.member, "name", for_update=True)
		for key, value in evaluate_access(self.business, self.branch, self.member, for_update=True).items():
			self.set(key, value)
		self.recorded_at = now_datetime()
		self.recorded_by = frappe.session.user

	def on_trash(self):
		frappe.throw(_("Conserve el historial de asistencias."), frappe.PermissionError)
