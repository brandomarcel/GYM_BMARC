import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, getdate, nowdate, validate_email_address

from gym_management.permissions import check_document, require_branch


class GymDocument(Document):
	def validate(self):
		check_document(self, "create" if self.is_new() else "write")
		previous = self.get_doc_before_save()
		immutable = ["business"]
		if self.doctype == "GYM Branch User":
			immutable += ["branch", "user"]
		if previous and any(previous.get(key) != self.get(key) for key in immutable):
			frappe.throw(
				_("No puede cambiar la pertenencia de un registro existente."), frappe.PermissionError
			)
		if previous:
			check_document(previous, "write")
		if self.status not in {"Activo", "Inactivo"}:
			frappe.throw(_("Estado de gimnasio no válido."))
		if self.doctype == "GYM Branch":
			self.validate_code("branch_code")
			if (
				self.establishment
				and frappe.db.get_value("FacturADA Establishment", self.establishment, "business")
				!= self.business
			):
				frappe.throw(_("El establecimiento no pertenece al negocio."), frappe.PermissionError)
		elif self.doctype == "GYM Branch User":
			require_branch(self.business, self.branch, allow_inactive=self.status == "Inactivo")
			if not frappe.db.exists(
				"FacturADA Business User", {"business": self.business, "user": self.user, "status": "Activo"}
			) or not frappe.db.get_value("User", self.user, "enabled"):
				frappe.throw(_("El usuario debe estar habilitado y asignado al negocio."))
		else:
			self.validate_code("member_code")
			self.first_name = cstr(self.first_name).strip()
			self.last_name = cstr(self.last_name).strip()
			self.full_name = " ".join(filter(None, [self.first_name, self.last_name]))
			if not self.first_name or not self.last_name:
				frappe.throw(_("Indique nombres y apellidos del socio."))
			if self.email:
				validate_email_address(self.email, throw=True)
			if self.birth_date and getdate(self.birth_date) > getdate(nowdate()):
				frappe.throw(_("La fecha de nacimiento no puede estar en el futuro."))

	def validate_code(self, fieldname):
		self.set(fieldname, cstr(self.get(fieldname)).strip().upper())
		if not self.get(fieldname):
			frappe.throw(_("Indique un código."))

	def on_trash(self):
		check_document(self, "delete")
