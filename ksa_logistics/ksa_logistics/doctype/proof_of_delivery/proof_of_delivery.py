# -*- coding: utf-8 -*-
# Copyright (c) 2026, KSA Logistics and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import now_datetime


class ProofofDelivery(Document):
	def validate(self):
		"""Validate POD"""
		self.validate_job_record()
		self.set_defaults_from_job_assignment()
		self.calculate_discrepancies()
		self.validate_mandatory_fields()
	
	def validate_job_record(self):
		"""Validate job record and check for duplicate POD per assignment"""
		if not self.job_record:
			frappe.throw(_("Job Record is required"))
		
		# Check if POD already exists for this job assignment
		# Multiple PODs are allowed per job, but only one per job assignment
		if self.job_assignment_name:
			# Check if POD already exists for this specific job assignment
			existing = frappe.db.exists("Proof of Delivery", {
				"job_record": self.job_record,
				"job_assignment_name": self.job_assignment_name,
				"name": ["!=", self.name]
			})
			
			if existing:
				frappe.throw(_("Proof of Delivery already exists for this Job Assignment: {0}").format(existing))
		else:
			# Legacy: If no job_assignment_name, check if POD exists for job (backward compatibility)
			existing = frappe.db.exists("Proof of Delivery", {
				"job_record": self.job_record,
				"job_assignment_name": ["in", ["", None]],
				"name": ["!=", self.name]
			})
			
			if existing:
				frappe.msgprint(_("Warning: Proof of Delivery already exists for this job without assignment: {0}. Consider specifying a job_assignment_name for multiple PODs.").format(existing), indicator="orange")
	
	def set_defaults_from_job_assignment(self):
		"""Set expected cargo details from Job Assignment - PRIORITY: Job Assignment > Job Record"""
		if self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			
			# Initialize with None
			expected_packages = None
			expected_weight = None
			delivery_note = None
			waybill = None
			
			# FIRST: Try to get from Job Assignment if job_assignment_name is set
			job_assignment_found = False
			if self.job_assignment_name:
				for ja in job.job_assignment:
					if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
						job_assignment_found = True
						expected_packages = ja.number_of_packages
						expected_weight = ja.gross_weight_kg
						
						# Get delivery_note and waybill from Job Assignment
						delivery_note = getattr(ja, 'delivery_note_record', None)
						waybill = getattr(ja, 'waybill_reference', None)
						
						# If not in Job Assignment, try to get from database
						if not delivery_note:
							try:
								result = frappe.db.sql("""
									SELECT delivery_note_record, waybill_reference
									FROM `tabJob Assignment`
									WHERE parent = %s AND name = %s
									LIMIT 1
								""", (self.job_record, ja.name), as_dict=True)
								if result:
									delivery_note = result[0].get('delivery_note_record')
									waybill = result[0].get('waybill_reference')
							except Exception:
								pass
						
						break
			
			# FALLBACK: Use Job Record Package Details totals if Job Assignment not found or not set
			if not self.job_assignment_name or not job_assignment_found:
				expected_packages = job.number_of_packagescontainer_pallets
				expected_weight = job.gross_weight_kg
				# Also try to get from Job Record
				delivery_note = job.delivery_note_record
				waybill = job.waybill_reference
			
			# Set expected fields - ALWAYS set from Job Assignment if job_assignment_name is set AND row was found
			if self.job_assignment_name and job_assignment_found:
				# Force set from Job Assignment (even if None/empty, to clear any Job Record values)
				self.expected_packages = expected_packages
				self.expected_weight = expected_weight
			else:
				# Only set if not already set (for Job Record fallback)
				if not self.expected_packages and expected_packages:
					self.expected_packages = expected_packages
				if not self.expected_weight and expected_weight:
					self.expected_weight = expected_weight
			
			# Auto-populate delivery_note and waybill if not already set
			if delivery_note and not self.delivery_note:
				self.delivery_note = delivery_note
			if waybill and not self.waybill:
				self.waybill = waybill
	
	def on_update(self):
		"""Actions on save/update"""
		self.update_job_record()
		self.update_delivery_note()
		self.update_waybill()
	
	def calculate_discrepancies(self):
		"""Calculate discrepancies"""
		if self.expected_packages and self.delivered_packages:
			self.discrepancy = self.expected_packages - self.delivered_packages
		
		if self.expected_weight and self.delivered_weight:
			self.weight_variance = self.expected_weight - self.delivered_weight
	
	def validate_mandatory_fields(self):
		"""Validate required fields"""
		if self.pod_status == "Verified":
			# Auto-set verified_by and verification_date if not set
			if not self.verified_by:
				self.verified_by = frappe.session.user
			
			if not self.verification_date:
				self.verification_date = now_datetime()
		
		# Check for discrepancy remarks
		if self.discrepancy and self.discrepancy != 0:
			if not self.pod_remarks:
				frappe.throw(_("Remarks required for package discrepancy"))
		
		if self.cargo_condition != "Good":
			if not self.damage_details:
				frappe.throw(_("Damage details required"))
	
	def update_job_record(self):
		"""Update job assignment (and optionally job record) with POD reference"""
		if self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			
			# Update Job Assignment if job_assignment_name is provided
			if self.job_assignment_name:
				job_assignment_found = False
				for ja in job.job_assignment:
					if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
						job_assignment_found = True
						# Determine document status
						doc_status = "POD Received" if self.pod_status == "Submitted" else "Completed" if self.pod_status == "Verified" else ja.document_status or "Delivered"
						
						# Update the Job Assignment row
						frappe.db.set_value("Job Assignment", ja.name, {
							"pod_reference": self.name,
							"pod_status": self.pod_status,
							"document_status": doc_status
						}, update_modified=False)
						break
				
				if not job_assignment_found:
					frappe.msgprint(_("Job Assignment {0} not found in Job Record").format(self.job_assignment_name), indicator="orange")
			
			# Also update Job Record for backward compatibility (aggregate view)
			job.db_set({
				"pod_reference": self.name,
				"pod_status": self.pod_status,
				"pod_verified_date": self.verification_date if self.pod_status == "Verified" else None,
				"document_status": "POD Received" if self.pod_status == "Submitted" else "Completed" if self.pod_status == "Verified" else job.document_status,
				"job_status": "Completed" if self.pod_status == "Verified" and self.cargo_condition == "Good" else job.job_status
			}, update_modified=False)
	
	def update_delivery_note(self):
		"""Update delivery note"""
		if self.delivery_note:
			dn = frappe.get_doc("Delivery Note Record", self.delivery_note)
			dn.db_set("pod_reference", self.name, update_modified=False)
	
	def update_waybill(self):
		"""Update waybill"""
		if self.waybill:
			wb = frappe.get_doc("Waybill", self.waybill)
			wb.db_set("waybill_status", "Delivered", update_modified=False)

@frappe.whitelist()
def verify_pod(pod_name):
	"""Verify POD"""
	pod = frappe.get_doc("Proof of Delivery", pod_name)
	
	if pod.pod_status == "Verified":
		frappe.throw(_("POD already verified"))
	
	pod.pod_status = "Verified"
	pod.verified_by = frappe.session.user
	pod.verification_date = now_datetime()
	pod.save()
	
	# Update job to completed
	job = frappe.get_doc("Job Record", pod.job_record)
	job.db_set({
		"job_status": "Completed",
		"document_status": "Completed"
	}, update_modified=True)
	
	return {"success": True, "message": _("POD verified successfully")}

@frappe.whitelist()
def reject_pod(pod_name, reason):
	"""Reject POD"""
	pod = frappe.get_doc("Proof of Delivery", pod_name)
	
	pod.pod_status = "Rejected"
	pod.pod_remarks = f"REJECTED: {reason}\n\n{pod.pod_remarks or ''}"
	pod.save()
	
	return {"success": True, "message": _("POD rejected")}

