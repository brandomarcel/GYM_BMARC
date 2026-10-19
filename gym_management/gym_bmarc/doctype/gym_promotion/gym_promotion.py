import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, getdate

from gym_management.membership_rules import money
from gym_management.permissions import check_document


class GYMPromotion(Document):
	def validate(self):
		check_document(self, "create" if self.is_new() else "write")
		previous = self.get_doc_before_save()
		if previous and previous.business != self.business:
			frappe.throw(_("No puede trasladar una promoción a otro negocio."), frappe.PermissionError)
		plan = frappe.get_doc("GYM Membership Plan", self.plan)
		plan.check_permission("read")
		if plan.business != self.business:
			frappe.throw(_("El plan no pertenece al negocio."), frappe.PermissionError)
		self.promotion_name = cstr(self.promotion_name).strip()
		self.benefit_value = money(self.benefit_value)
		if self.status not in {"Activo", "Inactivo"}:
			frappe.throw(_("Estado de promoción no válido."))
		if (
			not self.promotion_name
			or not self.valid_from
			or not self.valid_until
			or getdate(self.valid_from) > getdate(self.valid_until)
		):
			frappe.throw(_("Indique nombre y un período de promoción válido."))
		if self.benefit_type not in {"Porcentaje", "Importe fijo"} or self.benefit_value <= 0:
			frappe.throw(_("Indique un descuento positivo de porcentaje o importe fijo."))
		if self.benefit_type == "Porcentaje" and self.benefit_value > 100:
			frappe.throw(_("El porcentaje no puede superar 100."))
		if self.benefit_type == "Importe fijo" and self.benefit_value > money(plan.price):
			frappe.throw(_("El descuento fijo no puede superar el precio del plan."))

	def on_trash(self):
		check_document(self, "delete")
