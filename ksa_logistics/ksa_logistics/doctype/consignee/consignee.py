# -*- coding: utf-8 -*-
# Copyright (c) 2026, KSA Logistics and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class Consignee(Document):
	def validate(self):
		"""Validate consignee"""
		if not self.consignee_name:
			frappe.throw(_("Consignee Name is required"))






