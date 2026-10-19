"""Individual campaign pricing with real permissions and immutable contracts."""

import json

import frappe
from frappe.client import get_list
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from gym_management.api.memberships import create_membership
from gym_management.api.promotions import list_promotions, quote_price
from gym_management.membership_rules import request_hash
from gym_management.tests import test_memberships


class TestPromotions(FrappeTestCase):
	def setUp(self):
		self.base = test_memberships.TestMemberships()
		self.base.setUp()
		self.addCleanup(self.base.doCleanups)
		self.fixture = self.base.fixture
		self.business, self.branch = self.base.business, self.base.branch
		self.plan = self.base.plan()
		self.promo = self.campaign()

	def campaign(self, **values):
		return frappe.get_doc(
			{
				"doctype": "GYM Promotion",
				"business": self.business,
				"plan": self.plan.name,
				"promotion_name": "Promoción de prueba",
				"status": "Activo",
				"valid_from": add_days(nowdate(), -1),
				"valid_until": add_days(nowdate(), 1),
				"benefit_type": "Porcentaje",
				"benefit_value": 20,
				**values,
			}
		).insert()

	def quote(self, **values):
		return quote_price(
			**{
				"business": self.business,
				"plan": self.plan.name,
				"origin_branch": self.branch,
				"promotion": self.promo.name,
				**values,
			}
		)

	def contract(self, submit=True, **values):
		return self.base.contract(self.plan, submit=submit, promotion=self.promo.name, **values)

	def test_reception_applies_campaign_without_manual_discount_permission(self):
		self.fixture.act_as()
		quote = self.quote()
		self.assertEqual(quote["price"], 30)
		self.assertEqual(quote["discount"], 6)
		self.assertEqual(quote["total"], 24)
		doc = self.contract(price=1, total=1, promotion_snapshot='{"forged": true}')
		self.assertEqual(doc.price, 30)
		self.assertEqual(doc.total, 24)
		self.assertEqual(json.loads(doc.promotion_snapshot)["applied_by"], frappe.session.user)
		with self.assertRaises(frappe.PermissionError):
			self.quote(promotion=None, discount=6, discount_reason="Manual")

	def test_fixed_discount_and_cent_rounding(self):
		self.promo.benefit_type = "Importe fijo"
		self.promo.benefit_value = 5
		self.promo.save()
		self.assertEqual(self.quote()["total"], 25)
		self.promo.benefit_type = "Porcentaje"
		self.promo.benefit_value = 12.35
		self.promo.save()
		self.assertEqual(str(self.quote()["discount"]), "3.71")

	def test_expired_inactive_and_future_campaigns_are_denied(self):
		for changes in (
			{"valid_until": add_days(nowdate(), -1)},
			{"status": "Inactivo"},
			{"valid_from": add_days(nowdate(), 1)},
		):
			old = self.promo.as_dict()
			self.promo.update(changes).save()
			with self.assertRaises(frappe.ValidationError):
				self.quote()
			with self.assertRaises(frappe.ValidationError):
				self.contract(submit=False)
			self.promo.update({key: old[key] for key in changes}).save()

	def test_campaign_configuration_requires_plan_management(self):
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			self.campaign()
		self.promo.benefit_value = 50
		with self.assertRaises(frappe.PermissionError):
			self.promo.save()
		self.assertEqual([row.name for row in get_list("GYM Promotion", fields=["name"])], [self.promo.name])

	def test_other_business_plan_and_unassigned_branch_cannot_be_used(self):
		other_plan = self.base.plan()
		with self.assertRaises(frappe.PermissionError):
			self.quote(plan=other_plan.name)
		self.fixture.act_as()
		with self.assertRaises(frappe.PermissionError):
			self.quote(origin_branch=self.fixture.other_branch.name)
		self.fixture.act_as(1)
		with self.assertRaises(frappe.PermissionError):
			self.quote()
		self.assertEqual(get_list("GYM Promotion", fields=["name"]), [])

	def test_confirmed_snapshot_survives_campaign_and_plan_changes(self):
		doc = self.contract()
		before = doc.promotion_snapshot
		self.promo.status = "Inactivo"
		self.promo.benefit_value = 50
		self.promo.save()
		self.plan.price = 100
		self.plan.save()
		doc.reload()
		self.assertEqual(doc.total, 24)
		self.assertEqual(doc.promotion_snapshot, before)
		doc.promotion_snapshot = "{}"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_changed_campaign_requires_review_before_confirmation(self):
		doc = self.contract(submit=False)
		self.promo.benefit_value = 50
		self.promo.save()
		with self.assertRaises(frappe.ValidationError):
			doc.submit()
		# Refresh the draft explicitly, then confirm the revised conditions.
		doc.reload()
		doc.save()
		self.assertEqual(doc.total, 15)
		doc.submit()
		self.assertEqual(doc.total, 15)

	def test_expiry_is_rechecked_when_confirming_saved_draft(self):
		doc = self.contract(submit=False)
		self.promo.valid_until = add_days(nowdate(), -1)
		self.promo.save()
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_invalid_values_and_stacked_discount_are_rejected(self):
		for amount in (-1, 0, 101, "NaN", "Infinity"):
			with self.assertRaises(frappe.ValidationError):
				self.campaign(benefit_value=amount)
		with self.assertRaises(frappe.ValidationError):
			self.campaign(benefit_type="Importe fijo", benefit_value=31)
		with self.assertRaises(frappe.ValidationError):
			self.quote(discount=7)

	def test_api_retry_preserves_original_contract_and_campaign(self):
		self.fixture.act_as()
		values = {
			"business": self.business,
			"member": self.base.member,
			"plan": self.plan.name,
			"origin_branch": self.branch,
			"start_date": nowdate(),
			"promotion": self.promo.name,
			"request_key": "promo-retry",
		}
		first = create_membership(values)
		self.assertEqual(first["name"], create_membership(values)["name"])
		frappe.set_user("Administrator")
		second = self.campaign(benefit_value=25)
		with self.assertRaises(frappe.ValidationError):
			create_membership({**values, "promotion": second.name})
		self.assertEqual(frappe.db.count("GYM Membership", {"request_key": "promo-retry"}), 1)

	def test_legacy_request_hash_without_promotion_is_unchanged(self):
		import hashlib

		values = {
			key: None
			for key in (
				"business",
				"member",
				"plan",
				"origin_branch",
				"previous_membership",
				"start_date",
				"payment_due_date",
				"discount",
				"discount_reason",
			)
		}
		values["discount"] = "0.00"
		old_hash = hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()
		self.assertEqual(request_hash({}), old_hash)

	def test_discovery_returns_only_eligible_campaigns(self):
		self.campaign(status="Inactivo")
		self.campaign(valid_from=add_days(nowdate(), 1))
		self.fixture.act_as()
		rows = list_promotions(self.business, self.plan.name, self.branch)
		self.assertEqual([row.name for row in rows], [self.promo.name])

	def test_full_discount_preserves_normal_price_and_grants_access_without_money(self):
		from gym_management.api.memberships import check_access

		self.promo.benefit_value = 100
		self.promo.save()
		doc = self.contract()
		self.assertEqual(doc.price, 30)
		self.assertEqual(doc.total, 0)
		self.assertEqual(check_access(self.business, self.branch, self.base.member)["result"], "Permitido")
		self.assertEqual(frappe.db.count("FacturADA Payment Receipt", {"business": self.business}), 0)

	def test_receipts_and_lite_draft_use_promotional_total(self):
		from facturada_lite.api.receipts import record_receipt

		from gym_management.api.memberships import check_access, payment_summary
		from gym_management.tests import test_invoicing

		billing = test_invoicing.TestInvoicing()
		billing.setUp()
		self.addCleanup(billing.doCleanups)
		plan = frappe.get_doc("GYM Membership Plan", billing.contract.plan)
		billing.contract.cancel()
		plan.payment_policy = "Abonos"
		plan.minimum_percentage = 50
		plan.save()
		promo = self.campaign(business=billing.business, plan=plan.name)
		contract = billing.base.contract(plan=plan, promotion=promo.name)
		billing.values["membership"] = contract.name
		request = billing.request()
		self.assertEqual(request["invoice_total"], 24)
		record_receipt(
			{
				"business": billing.business,
				"source_doctype": "GYM Membership",
				"source_name": contract.name,
				"amount": 12,
				"payment_method": "Transferencia",
				"reference": "TEST-PROMOTION",
				"request_key": "promo-paid",
			}
		)
		self.assertEqual(payment_summary(contract)["outstanding"], 12)
		self.assertEqual(
			check_access(billing.business, billing.base.branch, contract.member)["result"], "Permitido"
		)
		self.assertEqual(frappe.db.count("FacturADA Payment Receipt", {"business": billing.business}), 1)
