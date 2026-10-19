import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, nowdate

from gym_management.membership_rules import (
	POLICY_FIELDS,
	end_date,
	request_hash,
	validate_branches,
	validate_policies,
)
from gym_management.permissions import check_document, require_access


class GYMMembership(Document):
	def save(self, *args, **kwargs):
		# All contract transitions take the member lock before Frappe locks the
		# contract row. Receipts and attendance use the same order.
		check_document(self, "create" if self.is_new() else "write")
		if frappe.db.exists("GYM Member", {"name": self.member, "business": self.business}):
			frappe.db.get_value("GYM Member", self.member, "name", for_update=True)
		return super().save(*args, **kwargs)

	def validate(self):
		check_document(self, "create" if self.is_new() else "write")
		previous = self.get_doc_before_save()
		if self.is_new():
			self.request_key = self.request_key or frappe.generate_hash(length=32)
			self.request_hash = request_hash(self)
		if previous:
			check_document(previous, "write")
			if previous.business != self.business or previous.member != self.member:
				frappe.throw(
					_("No puede cambiar el negocio o el socio del contrato."), frappe.PermissionError
				)
			if self.request_key != previous.request_key or self.request_hash != previous.request_hash:
				frappe.throw(_("No puede cambiar la identidad de la contratación."), frappe.PermissionError)
		member = frappe.get_doc("GYM Member", self.member)
		member.check_permission("read")
		plan = frappe.get_doc("GYM Membership Plan", self.plan)
		plan.check_permission("read")
		if member.business != self.business or plan.business != self.business:
			frappe.throw(_("El socio y el plan deben pertenecer al negocio."), frappe.PermissionError)
		if member.status != "Activo" or plan.status != "Activo":
			frappe.throw(_("El socio y el plan deben estar activos."))
		for field in POLICY_FIELDS:
			self.set(field, plan.get(field))
		self.set("branches", [{"branch": row.branch} for row in plan.branches])
		validate_policies(self)
		validate_branches(self)
		from gym_management.promotions import apply_price

		apply_price(self, plan)
		if self.previous_membership:
			old = frappe.get_doc("GYM Membership", self.previous_membership)
			old.check_permission("read")
			if old.business != self.business or old.member != self.member or old.docstatus != 1:
				frappe.throw(_("El contrato anterior no corresponde a una membresía confirmada del socio."))
			if self.renewal_mode == "Continua":
				self.start_date = add_days(old.end_date, 1)
		if getdate(self.start_date) < getdate(nowdate()):
			require_access(self.business, "gym.memberships.backdate")
		self.end_date = end_date(self.start_date, self.duration, self.duration_unit)
		self.payment_due_date = self.payment_due_date or self.start_date
		if getdate(self.payment_due_date) > getdate(self.end_date):
			frappe.throw(_("La fecha límite de pago no puede superar el fin del contrato."))
		# Approval is a separate, explicit action after confirmation.
		if self.credit_approved or self.credit_approved_by:
			frappe.throw(_("Confirme primero el contrato y luego autorice el crédito."))

	def before_submit(self):
		check_document(self, "submit")
		frappe.db.get_value("GYM Member", self.member, "name", for_update=True)
		if frappe.db.get_value(
			"GYM Membership",
			{
				"business": self.business,
				"member": self.member,
				"docstatus": 1,
				"name": ["!=", self.name],
				"start_date": ["<=", self.end_date],
				"end_date": [">=", self.start_date],
			},
			"name",
			for_update=True,
		):
			frappe.throw(_("El socio ya tiene una membresía confirmada que coincide con estas fechas."))

	def before_cancel(self):
		check_document(self, "cancel")
		frappe.db.get_value("GYM Member", self.member, "name", for_update=True)
		from gym_management.api.memberships import payment_summary

		request = frappe.db.get_value("GYM Billing Request", {"membership": self.name}, "emission_access_key")
		if request:
			frappe.throw(
				_(
					"El contrato tiene una identidad fiscal reservada. Resuelva primero su corrección fiscal sin borrar el historial."
				)
			)

		if payment_summary(self, for_update=True)["paid"] > 0:
			frappe.throw(_("Debe resolver los cobros del contrato antes de cancelarlo."))

	def before_update_after_submit(self):
		check_document(self, "write")
		require_access(self.business, "gym.credit.approve")
		if self.payment_policy != "Credito" or not (self.credit_reason or "").strip():
			frappe.throw(_("La autorización requiere condición de crédito y un motivo."))
		self.credit_approved_by = frappe.session.user

	def on_trash(self):
		check_document(self, "delete")
		if self.docstatus != 0:
			frappe.throw(_("Conserve el historial de contratos confirmados y cancelados."))
