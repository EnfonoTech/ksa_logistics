# -*- coding: utf-8 -*-
# Copyright (c) 2026, KSA Logistics and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class Shipper(Document):
	def validate(self):
		"""Validate shipper"""
		if not self.shipper_name:
			frappe.throw(_("Shipper Name is required"))






