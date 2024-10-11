# Copyright (c) 2024, S/N and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class Customer(Document):
    def before_save(self):
        if self.first_name and self.last_name:
            self.full_name = f"{self.first_name} {self.last_name}".upper()
