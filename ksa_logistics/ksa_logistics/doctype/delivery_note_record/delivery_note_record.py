# -*- coding: utf-8 -*-
# Copyright (c) 2026, KSA Logistics and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import now_datetime


class DeliveryNoteRecord(Document):
	def validate(self):
		"""Validate delivery note"""
		self.validate_job_record()
		self.set_defaults_from_job()
		self.calculate_totals()
	
	def set_defaults_from_job(self):
		"""Auto-populate cargo details from job record and job assignment"""
		if self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			
			# Set cargo details - PRIORITY: Job Assignment > Job Record Package Details
			cargo_description = None
			hs_code = None
			
			# FIRST: Try to get from Job Assignment if job_assignment_name is set
			job_assignment_found = False
			if self.job_assignment_name:
				for ja in job.job_assignment:
					if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
						job_assignment_found = True
						cargo_description = ja.cargo_description
						hs_code = ja.hs_code
						break
			
			# FALLBACK: Use Job Record Package Details totals if Job Assignment not found or not set
			if not self.job_assignment_name or not job_assignment_found:
				cargo_description = job.hs_description
				hs_code = job.hs_code
			
			# Set cargo fields - ALWAYS set from Job Assignment if job_assignment_name is set AND row was found
			if self.job_assignment_name and job_assignment_found:
				self.cargo_description = cargo_description
				self.hs_code = hs_code
			else:
				# Only set if not already set (for Job Record fallback)
				if not self.cargo_description and cargo_description:
					self.cargo_description = cargo_description
				if not self.hs_code and hs_code:
					self.hs_code = hs_code
	
	def on_update(self):
		"""Actions on save/update"""
		self.update_job_record()
		if self.delivery_status == "Delivered" and self.receiver_signature:
			self.auto_create_pod()
	
	def validate_job_record(self):
		"""Validate job record and check for duplicate delivery note per assignment"""
		if not self.job_record:
			frappe.throw(_("Job Record is required"))
		
		# Check if delivery note already exists for this job assignment
		# Multiple delivery notes are allowed per job, but only one per job assignment
		if self.job_assignment_name:
			# Check if delivery note already exists for this specific job assignment
			existing = frappe.db.exists("Delivery Note Record", {
				"job_record": self.job_record,
				"job_assignment_name": self.job_assignment_name,
				"name": ["!=", self.name]
			})
			
			if existing:
				frappe.throw(_("Delivery Note already exists for this Job Assignment: {0}").format(existing))
		else:
			# Legacy: If no job_assignment_name, check if delivery note exists for job (backward compatibility)
			existing = frappe.db.exists("Delivery Note Record", {
				"job_record": self.job_record,
				"job_assignment_name": ["in", ["", None]],
				"name": ["!=", self.name]
			})
			
			if existing:
				frappe.msgprint(_("Warning: Delivery Note already exists for this job without assignment: {0}. Consider specifying a job_assignment_name for multiple delivery notes.").format(existing), indicator="orange")
	
	def calculate_totals(self):
		"""Calculate totals including CBM"""
		total_packages = 0
		total_weight = 0.0
		total_volume = 0.0
		
		for item in self.delivery_items:
			total_packages += item.quantity or 0
			total_weight += item.weight or 0
			# Calculate CBM for this item if dimensions are provided
			if item.length_cm and item.width_cm and item.height_cm:
				# CBM = (L × W × H) / 1,000,000 (convert cm³ to m³)
				item_cbm = (item.length_cm * item.width_cm * item.height_cm) / 1000000.0
				# Multiply by quantity
				item_cbm = item_cbm * (item.quantity or 1)
				item.cbm = item_cbm
				total_volume += item_cbm
			elif item.cbm:
				# Use manually entered CBM
				total_volume += item.cbm * (item.quantity or 1)
			elif item.volume:
				# Fallback to volume field if cbm not calculated
				total_volume += item.volume or 0
		
		self.total_packages = total_packages
		self.total_weight = total_weight
		self.total_volume = total_volume
	
	def update_job_record(self):
		"""Update job assignment (and optionally job record) with delivery note reference"""
		if self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			
			# Update Job Assignment if job_assignment_name is provided
			if self.job_assignment_name:
				job_assignment_found = False
				for ja in job.job_assignment:
					if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
						job_assignment_found = True
						# Update the Job Assignment row
						frappe.db.set_value("Job Assignment", ja.name, {
							"delivery_note_record": self.name,
							"delivery_status": self.delivery_status,
							"document_status": "Delivered" if self.delivery_status == "Delivered" else ja.document_status or "Arrived"
						}, update_modified=False)
						break
				
				if not job_assignment_found:
					frappe.msgprint(_("Job Assignment {0} not found in Job Record").format(self.job_assignment_name), indicator="orange")
			
			# Also update Job Record for backward compatibility (aggregate view)
			job.db_set({
				"delivery_note_record": self.name,
				"delivery_status": self.delivery_status,
				"document_status": "Delivered" if self.delivery_status == "Delivered" else job.document_status
			}, update_modified=False)
	
	def auto_create_pod(self):
		"""Auto-create POD template if delivery is completed"""
		if self.delivery_status == "Delivered" and self.receiver_signature and not self.pod_reference:
			# Check if POD already exists for this job assignment
			# Multiple PODs are allowed per job, but only one per job assignment
			if self.job_assignment_name:
				existing_pod = frappe.db.exists("Proof of Delivery", {
					"job_record": self.job_record,
					"job_assignment_name": self.job_assignment_name
				})
			else:
				# Legacy: Check for POD without assignment
				existing_pod = frappe.db.exists("Proof of Delivery", {
					"job_record": self.job_record,
					"job_assignment_name": ["in", ["", None]]
				})
			
			if not existing_pod:
				# Create POD
				pod = frappe.new_doc("Proof of Delivery")
				pod.job_record = self.job_record
				pod.delivery_note = self.name
				pod.waybill = self.waybill
				pod.job_assignment_name = self.job_assignment_name  # Pass job_assignment_name to POD
				pod.pod_date = self.delivery_date
				pod.actual_delivery_date = self.delivery_date
				pod.actual_delivery_time = self.delivery_time
				
				# Copy receiver details
				pod.receiver_name = self.receiver_name
				pod.receiver_id_number = self.receiver_id
				pod.receiver_designation = self.receiver_designation
				
				# Set job_assignment_name for POD to get cargo from Job Assignment
				pod.job_assignment_name = self.job_assignment_name
				
				# Copy delivered cargo details
				pod.delivered_packages = self.total_packages
				pod.delivered_weight = self.total_weight
				pod.cargo_condition = "Good"
				
				# Note: expected_packages and expected_weight will be set from Job Assignment
				# via POD's set_defaults_from_job_assignment() method during validate
				
				# Copy signature and photos
				if self.receiver_signature:
					pod.receiver_signature = self.receiver_signature
				
				if self.delivery_photos:
					for photo in self.delivery_photos:
						pod.append("delivery_photos", {
							"photo": photo.photo,
							"photo_type": photo.photo_type,
							"description": photo.description
						})
				
				pod.save()
				
				# Link POD to delivery note
				self.db_set("pod_reference", pod.name, update_modified=False)
				
				frappe.msgprint(_("POD {0} created automatically").format(pod.name))

@frappe.whitelist()
def get_delivery_details(job_record, job_assignment_name=None):
	"""Get delivery details from job and job assignment"""
	job = frappe.get_doc("Job Record", job_record)
	
	# Get consignee details
	consignee_name = None
	if job.consignee:
		consignee = frappe.get_doc("Consignee", job.consignee)
		consignee_name = consignee.consignee_name
	
	# Get cargo details - PRIORITY: Job Assignment > Job Record Package Details
	cargo_description = None
	hs_code = None
	
	if job_assignment_name:
		# Get cargo from Job Assignment
		for ja in job.job_assignment:
			if str(ja.name) == str(job_assignment_name) or str(ja.idx) == str(job_assignment_name):
				cargo_description = ja.cargo_description
				hs_code = ja.hs_code
				break
	
	# Fallback to Job Record if Job Assignment not found or not set
	if cargo_description is None:
		cargo_description = job.hs_description
	if hs_code is None:
		hs_code = job.hs_code
	
	return {
		"customer": job.customer,
		"consignee_name": consignee_name,
		"delivery_address": job.destination or job.delivery_address,
		"waybill": job.waybill_reference,
		# cargo_description and hs_code come from Job Assignment if available
		"cargo_description": cargo_description,
		"hs_code": hs_code
	}

