from frappe.core.doctype.file.file import File

from gym_management.permissions import FILE_DOCTYPES, file_permission, validate_file


class GymAwareFile(File):
	def before_insert(self):
		# Check before Frappe writes any blob, especially a public one, to disk.
		validate_file(self)
		super().before_insert()

	def validate(self):
		validate_file(self)
		super().validate()

	def is_downloadable(self):
		if self.attached_to_doctype in FILE_DOCTYPES:
			permission = file_permission(self, "read")
			if permission is not None:
				return bool(permission) and super().is_downloadable()
		return super().is_downloadable()
