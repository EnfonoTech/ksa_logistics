# Copyright (c) 2025, siva@enfono.in and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class JobRecord(Document):
	def validate(self):
		total_value = 0
		item_profit = 0
		if not hasattr(self, 'items') or not self.items:
			return
		for row in self.items:
			if not row.item:
				continue

			if self.get_valuation_rate_from == "Latest Purchase":
				row.valuation_rate = get_latest_purchase_rate(row.item)
				row.valuation_amount = row.quantity * row.valuation_rate
				row.profit = row.amount - row.valuation_amount

			elif self.get_valuation_rate_from == "Stock Ledger":
				row.valuation_rate = get_stock_valuation_rate(row.item)
				row.valuation_amount = row.quantity * row.valuation_rate
				row.profit = row.amount - row.valuation_amount

			else:
				row.valuation_rate = 0.0
				row.valuation_amount = row.quantity * row.valuation_rate
				row.profit = row.amount - row.valuation_amount
				
			total_value += row.valuation_amount
			item_profit += row.profit
		self.total_valuation = total_value
		self.item_profit = item_profit
		
		# Auto-update document status
		self.update_document_status()
		
		# Sync workflow vouchers from job assignments
		self.sync_workflow_vouchers()
	
	def sync_workflow_vouchers(self):
		"""Sync vouchers2 table with workflow documents from all job assignments"""
		if not self.job_assignment:
			return
		
		# Get existing vouchers that are NOT workflow-related (preserve other vouchers)
		workflow_doctypes = ["Collection Note", "Waybill", "Delivery Note Record", "Proof of Delivery"]
		existing_vouchers = [v for v in (self.vouchers2 or []) if v.link_type not in workflow_doctypes]
		
		# Clear all vouchers and rebuild
		self.vouchers2 = []
		
		# Add back existing non-workflow vouchers
		for v in existing_vouchers:
			self.append("vouchers2", v)
		
		# Add workflow vouchers from each assignment
		for idx, assignment in enumerate(self.job_assignment):
			assignment_label = assignment.driver_name or assignment.driver or f"Assignment {idx + 1}"
			assignment_suffix = f" ({assignment_label})"
			
			# Collection Note
			if assignment.collection_note:
				self.append("vouchers2", {
					"voucher_type": "Collection Note",
					"voucher_id": assignment.collection_note,
					"name1": assignment.collection_note + assignment_suffix,
					"link_type": "Collection Note",
					"voucher_record_link": assignment.collection_note,
					"status": assignment.collection_status or "Pending"
				})
			
			# Waybill
			if assignment.waybill_reference:
				self.append("vouchers2", {
					"voucher_type": "Waybill",
					"voucher_id": assignment.waybill_reference,
					"name1": assignment.waybill_reference + assignment_suffix,
					"link_type": "Waybill",
					"voucher_record_link": assignment.waybill_reference,
					"status": assignment.waybill_status or "Prepared"
				})
			
			# Delivery Note Record
			if assignment.delivery_note_record:
				self.append("vouchers2", {
					"voucher_type": "Delivery Note Record",
					"voucher_id": assignment.delivery_note_record,
					"name1": assignment.delivery_note_record + assignment_suffix,
					"link_type": "Delivery Note Record",
					"voucher_record_link": assignment.delivery_note_record,
					"status": assignment.delivery_status or "Pending"
				})
			
			# POD
			if assignment.pod_reference:
				self.append("vouchers2", {
					"voucher_type": "Proof of Delivery",
					"voucher_id": assignment.pod_reference,
					"name1": assignment.pod_reference + assignment_suffix,
					"link_type": "Proof of Delivery",
					"voucher_record_link": assignment.pod_reference,
					"status": assignment.pod_status or "Pending"
				})
	
	def update_document_status(self):
		"""Auto-update document status based on workflow progress"""
		if not self.document_status:
			self.document_status = "Job Created"
		
		# Update status based on collection
		if self.collection_required and not self.collection_note:
			if self.document_status == "Job Created":
				self.document_status = "Collection Scheduled"
		elif self.collection_note and self.collection_status == "Completed":
			if self.document_status in ["Job Created", "Collection Scheduled"]:
				self.document_status = "Collection Completed"
		
		# Update status based on waybill
		if self.waybill_reference:
			if self.document_status in ["Job Created", "Collection Completed"]:
				self.document_status = "Waybill Created"
			if self.waybill_status == "In Transit":
				self.document_status = "In Transit"
			elif self.waybill_status == "Arrived at Destination":
				self.document_status = "Arrived"
			elif self.waybill_status == "Delivered":
				self.document_status = "Delivered"
		
		# Update status based on delivery note
		if self.delivery_note_record:
			if self.delivery_status == "Delivered":
				self.document_status = "Delivered"
		
		# Update status based on POD
		if self.pod_reference:
			if self.pod_status == "Submitted":
				self.document_status = "POD Received"
			elif self.pod_status == "Verified":
				self.document_status = "Completed"


def get_latest_purchase_rate(item_code):
    result = frappe.db.sql("""
        SELECT pi_item.rate
        FROM `tabPurchase Invoice Item` pi_item
        JOIN `tabPurchase Invoice` pi ON pi.name = pi_item.parent
        WHERE pi_item.item_code = %s AND pi.docstatus = 1
        ORDER BY pi.posting_date DESC, pi.creation DESC
        LIMIT 1
    """, (item_code,), as_dict=1)
    return flt(result[0].rate) if result else 0.0



def get_stock_valuation_rate(item_code):
    result = frappe.db.sql("""
        SELECT valuation_rate
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s AND valuation_rate IS NOT NULL
        ORDER BY posting_date DESC, posting_time DESC, creation DESC
        LIMIT 1
    """, (item_code,), as_dict=1)
    return result[0].valuation_rate if result else 0.0


@frappe.whitelist()
def sync_workflow_vouchers(job_record):
	"""Sync vouchers2 table with workflow documents from job assignments"""
	job = frappe.get_doc("Job Record", job_record)
	job.sync_workflow_vouchers()
	job.save(ignore_permissions=True)
	return {"success": True, "message": "Vouchers synced successfully"}




		