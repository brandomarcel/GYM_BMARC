"""Read-only configuration checklist for the technical platform administrator."""

import frappe
from facturada_core.api.business import get_allowed_business_names, validate_business_access
from facturada_core.api.license import is_feature_enabled
from frappe import _


def technical_admin():
	user = frappe.session.user
	if (
		user == "Guest"
		or not frappe.db.get_value("User", user, "enabled")
		or "System Manager" not in frappe.get_roles(user)
	):
		frappe.throw(_("La configuración está reservada al administrador técnico."), frappe.PermissionError)


@frappe.whitelist(methods=["GET", "POST"])
def get_setup_businesses():
	technical_admin()
	names = get_allowed_business_names()
	return (
		frappe.get_all(
			"FacturADA Business",
			filters={"name": ["in", names]},
			fields=["name", "business_name"],
			order_by="business_name asc",
		)
		if names
		else []
	)


@frappe.whitelist(methods=["GET", "POST"])
def get_setup_checklist(business):
	technical_admin()
	validate_business_access(business)
	steps = []
	for key, title, doctype, filters in (
		(
			"subscription",
			_("Suscripción al software: habilitar GYM"),
			"FacturADA Business Subscription",
			{"business": business},
		),
		("branches", _("Sucursales activas"), "GYM Branch", {"business": business, "status": "Activo"}),
		(
			"users",
			_("Usuarios del negocio"),
			"FacturADA Business User",
			{"business": business, "status": "Activo"},
		),
		(
			"assignments",
			_("Personal asignado a sucursales"),
			"GYM Branch User",
			{"business": business, "status": "Activo"},
		),
		(
			"plans",
			_("Planes de membresía activos"),
			"GYM Membership Plan",
			{"business": business, "status": "Activo"},
		),
	):
		count = frappe.db.count(doctype, filters)
		ready = bool(count) and (key != "subscription" or is_feature_enabled("gym", business=business))
		steps.append(
			{
				"key": key,
				"title": title,
				"doctype": doctype,
				"count": count,
				"ready": ready,
				"filters": filters,
			}
		)
	return {
		"business": business,
		"steps": steps,
		"payments_available": "facturada_lite" in frappe.get_installed_apps(),
		"cash_available": "facturada_restaurante" in frappe.get_installed_apps(),
		"note": _(
			"Esta lista comprueba registros básicos. Verifique permisos y pruebe el acceso con cada usuario antes de operar."
		),
	}
