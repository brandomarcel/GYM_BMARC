"""Application use case shared by RPC and the Frappe document lifecycle."""

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

import frappe
from facturada_core.api.business import require_business_permission
from frappe import _
from frappe.utils import now_datetime

from gym_management.permissions import check_document

REQUEST_DOCTYPE = "GYM Billing Request"
INPUT_FIELDS = ("membership", "customer", "service", "pos_terminal", "price_basis")


@dataclass(frozen=True)
class PreparedDraft:
	payload: dict
	total: str
	tax_rate: str


class DraftGateway(Protocol):
	def prepare(self, membership, selections: dict) -> PreparedDraft: ...

	def create(self, request, draft: PreparedDraft) -> str: ...


def gateway() -> DraftGateway:
	# GYM remains installable without Lite. Only this adapter imports Lite.
	from gym_management.billing.lite import LiteDraftGateway

	return LiteDraftGateway()


def authorized_membership(name, lock=False):
	doc = frappe.get_doc("GYM Membership", name)
	check_document(doc, "read")
	require_business_permission(doc.business, "billing.create")
	if lock:
		frappe.db.get_value("GYM Member", doc.member, "name", for_update=True)
		doc = frappe.get_doc("GYM Membership", name, for_update=True)
		check_document(doc, "read")
	if doc.docstatus != 1:
		frappe.throw(_("La membresía debe estar confirmada para preparar su factura."))
	return doc


def fingerprint(values):
	return hashlib.sha256(
		json.dumps({key: values.get(key) or None for key in INPUT_FIELDS}, sort_keys=True).encode()
	).hexdigest()


def prepare_document(doc, adapter=None):
	if any(doc.get(field.fieldname) for field in doc.meta.fields if field.fieldname.startswith("emission_")):
		frappe.throw(_("Los datos de emisión solo se preparan desde el flujo fiscal autorizado."))
	membership = authorized_membership(doc.membership, lock=True)
	if doc.business and doc.business != membership.business:
		frappe.throw(_("La solicitud no pertenece al negocio del contrato."), frappe.PermissionError)
	doc.business = membership.business
	doc.origin_branch = membership.origin_branch
	doc.request_key = (doc.request_key or "").strip()
	if not doc.request_key or len(doc.request_key) > 100:
		frappe.throw(_("Indique una clave de reintento de hasta 100 caracteres."))
	# Serialize all request origins, including generic Frappe insert calls.
	if frappe.db.get_value(REQUEST_DOCTYPE, {"membership": doc.membership}, "name", for_update=True):
		frappe.throw(_("Este contrato ya tiene una solicitud fiscal. Abra su borrador existente."))
	adapter = adapter or gateway()
	draft = adapter.prepare(membership, doc.as_dict())
	doc.request_hash = fingerprint(doc)
	doc.commercial_total = membership.total
	doc.invoice_total = draft.total
	doc.tax_rate = draft.tax_rate
	doc.environment = draft.payload["environment"]
	doc.draft_payload = json.dumps(draft.payload, default=str, sort_keys=True)
	doc.invoice = None
	doc.prepared_by = frappe.session.user
	doc.prepared_at = now_datetime()
	doc._draft = draft


def persist_draft(doc):
	# before validation always reconstructs this object from authorized state.
	doc.db_set("invoice", gateway().create(doc, doc._draft))


def create_request(values):
	values = frappe._dict(values)
	membership = authorized_membership(values.membership, lock=True)
	key = (values.request_key or "").strip()
	if not key or len(key) > 100:
		frappe.throw(_("Indique una clave de reintento de hasta 100 caracteres."))
	digest = fingerprint(values)
	existing = frappe.db.get_value(
		REQUEST_DOCTYPE, {"business": membership.business, "request_key": key}, "name", for_update=True
	) or frappe.db.get_value(REQUEST_DOCTYPE, {"membership": membership.name}, "name", for_update=True)
	if existing:
		doc = frappe.get_doc(REQUEST_DOCTYPE, existing, for_update=True)
		doc.check_permission("read")
		if doc.request_hash != digest:
			frappe.throw(_("Ya existe una solicitud fiscal con otros datos; no se creará otra factura."))
		invoice = (
			frappe.db.get_value(
				"FacturADA Lite Invoice",
				doc.invoice,
				["business", "source_doctype", "source_name"],
				as_dict=True,
				for_update=True,
			)
			if doc.invoice
			else None
		)
		if not invoice or (invoice.business, invoice.source_doctype, invoice.source_name) != (
			doc.business,
			doc.doctype,
			doc.name,
		):
			frappe.throw(_("La solicitud necesita revisión: su borrador fiscal no está disponible."))
		return doc
	doc = frappe.get_doc(
		{
			"doctype": REQUEST_DOCTYPE,
			"business": membership.business,
			"origin_branch": membership.origin_branch,
			**{field: values.get(field) for field in INPUT_FIELDS},
			"request_key": key,
		}
	)
	return doc.insert()
