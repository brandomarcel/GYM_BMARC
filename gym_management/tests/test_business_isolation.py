"""Exercise Frappe's real permission pipeline; no provider calls or production data."""

import uuid

import frappe
from facturada_core.api.business import get_available_business_roles
from frappe.client import get, get_list, insert, save
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from gym_management.api.context import business_link_query, business_query


class TestBusinessIsolation(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.token = uuid.uuid4().hex[:10]
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		self.businesses = []
		self.users = []
		self.branches = []
		self.members = []
		for index in range(2):
			business = frappe.get_doc(
				{
					"doctype": "FacturADA Business",
					"business_name": f"GYM TEST {self.token} {index}",
					"tax_id": str(uuid.uuid4().int)[:13],
					"is_demo": 1,
				}
			).insert()
			self.businesses.append(business)
			frappe.get_doc(
				{
					"doctype": "FacturADA Business Subscription",
					"business": business.name,
					"plan_code": "GYM_TEST",
					"plan_name": "Prueba GYM",
					"status": "Activo",
					"subscription_start": nowdate(),
					"enable_gym": 1,
					"enable_billing": 0,
				}
			).insert()
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": f"gym-{self.token}-{index}@example.invalid",
					"first_name": "Recepción",
					"user_type": "System User",
					"send_welcome_email": 0,
				}
			).insert()
			self.users.append(user)
			frappe.get_doc(
				{
					"doctype": "FacturADA Business User",
					"business": business.name,
					"user": user.name,
					"business_role": "Recepcionista",
					"status": "Activo",
				}
			).insert()
			branch = frappe.get_doc(
				{
					"doctype": "GYM Branch",
					"business": business.name,
					"branch_code": "CENTRO",
					"branch_name": f"Centro {index}",
				}
			).insert()
			self.branches.append(branch)
			frappe.get_doc(
				{
					"doctype": "GYM Branch User",
					"business": business.name,
					"branch": branch.name,
					"user": user.name,
				}
			).insert()
			self.members.append(self.make_member(index))
		self.other_branch = frappe.get_doc(
			{
				"doctype": "GYM Branch",
				"business": self.businesses[0].name,
				"branch_code": "NORTE",
				"branch_name": "Norte",
			}
		).insert()
		self.other_member = self.make_member(0, home_branch=self.other_branch.name, member_code="NORTE")

	def make_member(self, index, **overrides):
		return frappe.get_doc(
			{
				"doctype": "GYM Member",
				"business": self.businesses[index].name,
				"home_branch": self.branches[index].name,
				"member_code": "SOCIO-1",
				"first_name": "Socio",
				"last_name": "Prueba",
				**overrides,
			}
		).insert()

	def act_as(self, index=0):
		frappe.set_user(self.users[index].name)

	def test_reception_has_desk_role_without_fiscal_permissions(self):
		from facturada_core.api.business_permissions import permissions_for_role

		self.assertIn("GYM User", frappe.get_roles(self.users[0].name))
		self.assertNotIn("System Manager", frappe.get_roles(self.users[0].name))
		self.assertNotIn("billing.create", permissions_for_role("Recepcionista"))
		roles = get_available_business_roles(self.businesses[0].name)["data"]
		self.assertIn("Recepcionista", [r["name"] for r in roles])

	def test_lists_and_known_ids_obey_business_and_branch(self):
		self.act_as()
		rows = get_list("GYM Member", fields=["name"])
		self.assertEqual([row.name for row in rows], [self.members[0].name])
		self.assertEqual(get("GYM Member", self.members[0].name).name, self.members[0].name)
		for member in (self.members[1], self.other_member):
			with self.assertRaises(frappe.PermissionError):
				get("GYM Member", member.name)
		self.assertEqual(
			[row.name for row in get_list("GYM Branch", fields=["name"])], [self.branches[0].name]
		)
		assignments = get_list("GYM Branch User", fields=["user", "business"])
		self.assertEqual({row.user for row in assignments}, {self.users[0].name})

	def test_create_update_delete_and_crafted_links(self):
		self.act_as()
		created = insert(
			{
				"doctype": "GYM Member",
				"business": self.businesses[0].name,
				"home_branch": self.branches[0].name,
				"member_code": "NEW",
				"first_name": "Nueva",
				"last_name": "Persona",
			}
		)
		self.assertEqual(created["full_name"], "Nueva Persona")
		for business, branch in (
			(self.businesses[1].name, self.branches[1].name),
			(self.businesses[0].name, self.branches[1].name),
			(self.businesses[0].name, self.other_branch.name),
		):
			with self.assertRaises(frappe.PermissionError):
				insert(
					{
						"doctype": "GYM Member",
						"business": business,
						"home_branch": branch,
						"member_code": "ATTACK",
						"first_name": "No",
						"last_name": "Permitido",
					}
				)
		with self.assertRaises(frappe.PermissionError):
			save({**self.members[1].as_dict(), "phone": "000"})
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("GYM Member", self.members[1].name)
		with self.assertRaises(frappe.PermissionError):
			save({**self.members[0].as_dict(), "business": self.businesses[1].name})

	def test_cannot_grant_self_branch_or_create_branches(self):
		self.act_as()
		with self.assertRaises(frappe.PermissionError):
			insert(
				{
					"doctype": "GYM Branch User",
					"business": self.businesses[0].name,
					"branch": self.other_branch.name,
					"user": self.users[0].name,
				}
			)
		with self.assertRaises(frappe.PermissionError):
			insert(
				{
					"doctype": "GYM Branch",
					"business": self.businesses[0].name,
					"branch_code": "NEW",
					"branch_name": "No permitida",
				}
			)

	def test_business_admin_sees_all_own_branches_but_not_other_businesses(self):
		assignment = frappe.get_doc(
			"FacturADA Business User", {"business": self.businesses[0].name, "user": self.users[0].name}
		)
		assignment.business_role = "Administrador"
		assignment.save()
		self.act_as()
		self.assertEqual(
			{r.name for r in get_list("GYM Member", fields=["name"])},
			{self.members[0].name, self.other_member.name},
		)
		with self.assertRaises(frappe.PermissionError):
			get("GYM Member", self.members[1].name)

	def test_manager_is_still_restricted_to_assigned_branches(self):
		assignment = frappe.get_doc(
			"FacturADA Business User", {"business": self.businesses[0].name, "user": self.users[0].name}
		)
		assignment.business_role = "Gerente"
		assignment.save()
		self.act_as()
		self.assertEqual([r.name for r in get_list("GYM Member", fields=["name"])], [self.members[0].name])
		with self.assertRaises(frappe.PermissionError):
			get("GYM Member", self.other_member.name)

	def test_revocation_license_expiration_and_disabled_business(self):
		business = self.businesses[0].name
		sub = frappe.get_doc("FacturADA Business Subscription", {"business": business})
		for values in (
			{"enable_gym": 0},
			{"subscription_end": add_days(nowdate(), -1)},
			{"status": "Suspendido"},
		):
			frappe.set_user("Administrator")
			frappe.db.set_value(sub.doctype, sub.name, values)
			self.act_as()
			self.assertEqual(get_list("GYM Member", fields=["name"]), [])
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				get("GYM Member", self.members[0].name)
			frappe.set_user("Administrator")
			frappe.db.set_value(
				sub.doctype, sub.name, {"enable_gym": 1, "subscription_end": None, "status": "Activo"}
			)
		for doctype, filters, values in (
			("GYM Branch User", {"user": self.users[0].name}, {"status": "Inactivo"}),
			("FacturADA Business User", {"user": self.users[0].name}, {"status": "Inactivo"}),
			("FacturADA Business", {"name": business}, {"status": "Suspendido"}),
		):
			frappe.set_user("Administrator")
			frappe.db.set_value(doctype, filters, values)
			self.act_as()
			self.assertEqual(get_list("GYM Member", fields=["name"]), [])
			with self.assertRaises(frappe.PermissionError):
				get("GYM Member", self.members[0].name)
			frappe.set_user("Administrator")
			frappe.db.set_value(doctype, filters, {"status": "Activo"})

	def test_multi_business_and_multi_branch_assignment(self):
		frappe.get_doc(
			{
				"doctype": "FacturADA Business User",
				"business": self.businesses[1].name,
				"user": self.users[0].name,
				"business_role": "Recepcionista",
			}
		).insert()
		for business, branch in (
			(self.businesses[1].name, self.branches[1].name),
			(self.businesses[0].name, self.other_branch.name),
		):
			frappe.get_doc(
				{
					"doctype": "GYM Branch User",
					"business": business,
					"branch": branch,
					"user": self.users[0].name,
				}
			).insert()
		self.act_as()
		self.assertEqual(len(get_list("GYM Member", fields=["name"])), 3)
		self.assertEqual(len(get_list("GYM Member", filters={"business": self.businesses[1].name})), 1)

	def test_codes_are_unique_per_business_and_parent_cannot_change(self):
		with self.assertRaises(frappe.UniqueValidationError):
			self.make_member(0)
		member = self.members[0]
		member.business = self.businesses[1].name
		member.home_branch = self.branches[1].name
		with self.assertRaises(frappe.PermissionError):
			member.save()

	def test_private_file_boundary_even_if_file_owned_by_attacker(self):
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"gym-{self.token}.txt",
				"is_private": 1,
				"content": self.token,
				"attached_to_doctype": "GYM Member",
				"attached_to_name": self.members[1].name,
			}
		).insert()
		frappe.db.set_value("File", file.name, "owner", self.users[0].name)
		self.act_as()
		with self.assertRaises(frappe.PermissionError):
			get("File", file.name)
		self.assertNotIn(file.name, [r.name for r in get_list("File", fields=["name"])])
		from frappe.core.doctype.file.utils import find_file_by_url

		self.assertIsNone(find_file_by_url(file.file_url))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "alias.txt",
					"is_private": 1,
					"file_url": file.file_url,
				}
			).insert()
		frappe.set_user("Administrator")
		file.reload()
		file.is_private = 0
		with self.assertRaises(frappe.PermissionError):
			file.save()
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "DocShare",
					"share_doctype": "GYM Member",
					"share_name": self.members[1].name,
					"user": self.users[0].name,
					"read": 1,
				}
			).insert()

	def test_link_search_is_scoped_and_does_not_list_other_users(self):
		self.act_as()
		rows = business_query("FacturADA Business", "", "name", 0, 20, {})
		self.assertEqual({r[0] for r in rows}, {self.businesses[0].name})
		with self.assertRaises(frappe.PermissionError):
			business_link_query("User", "", "name", 0, 20, {"business": self.businesses[0].name})

	def test_guest_denied(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			get("GYM Member", self.members[0].name)

	def test_legacy_api_cannot_impersonate_another_user(self):
		from gym_management.public.apiRest import get_company_and_plans

		self.act_as()
		with self.assertRaises(frappe.PermissionError):
			get_company_and_plans(self.users[1].name)
