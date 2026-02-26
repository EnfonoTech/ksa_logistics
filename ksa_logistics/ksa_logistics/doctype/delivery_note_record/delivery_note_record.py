# -*- coding: utf-8 -*-
# Copyright (c) 2026, KSA Logistics and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import now_datetime, flt


class DeliveryNoteRecord(Document):
	def validate(self):
		"""Validate delivery note"""
		# When waybill is set, fetch all details from Waybill first (internal reference)
		if self.waybill:
			self.set_defaults_from_waybill()
			if not self.job_record:
				wb = frappe.get_doc("Waybill", self.waybill)
				if getattr(wb, "job_record", None):
					self.job_record = wb.job_record
				if getattr(wb, "job_assignment_name", None):
					self.job_assignment_name = wb.job_assignment_name
		else:
			self.set_defaults_from_job()
		self.validate_job_record()
	
	def set_defaults_from_waybill(self):
		"""Auto-populate all fields from linked Waybill (same structure as Waybill; internal reference)."""
		if not self.waybill:
			return
		wb = frappe.get_doc("Waybill", self.waybill)
		# All fields that exist on both Waybill and Delivery Note Record (same names)
		waybill_copy_fields = (
			"customer", "transport_mode", "shipment_type", "waybill_date", "current_location", "truck_number",
			"shipper_name", "shipper_address", "consignee_name", "consignee_address",
			"receiver_name", "receiver_contact_number", "container_number", "number_of_packages",
			"gross_weight", "volume_cbm", "cargo_description", "hs_code", "origin", "destination",
			"vehicle", "driver", "vehicle_plate_number", "driver_name", "driver_mobile",
			"gate_pass_number", "truck_type",
			"airline", "flight_number", "mawb_number", "hawb_number", "departure_airport", "arrival_airport",
			"shipping_line", "vessel_name", "voyage_number", "bl_number", "mbl_number", "hbl_number",
			"port_of_loading", "port_of_discharge",
			"job_record", "job_assignment_name"
		)
		for field in waybill_copy_fields:
			if not hasattr(self, field):
				continue
			val = getattr(wb, field, None)
			if val is not None:
				setattr(self, field, val)
		# Waybill number: use waybill's name or waybill_number field
		if hasattr(self, "waybill_number"):
			self.waybill_number = getattr(wb, "waybill_number", None) or wb.name
	
	def set_defaults_from_job(self):
		"""Auto-populate cargo details from job record and job assignment (when no waybill linked)"""
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
	
	def validate_job_record(self):
		"""Require either Waybill or Job Record. Check duplicate delivery note per assignment when linked to job."""
		if not self.waybill and not self.job_record:
			frappe.throw(_("Waybill or Job Record is required"))
		if not self.job_record:
			return
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
				
				# Copy delivered cargo details (Delivery Note uses number_of_packages, gross_weight like Waybill)
				pod.delivered_packages = getattr(self, "number_of_packages", None) or getattr(self, "total_packages", None)
				pod.delivered_weight = flt(getattr(self, "gross_weight", None) or getattr(self, "total_weight", None))
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
def get_delivery_details_from_waybill(waybill_name):
	"""Return all Waybill fields to pre-fill Delivery Note Record (same structure as Waybill)."""
	if not waybill_name:
		return {}
	wb = frappe.get_doc("Waybill", waybill_name)
	fields = (
		"job_record", "job_assignment_name", "customer", "transport_mode", "shipment_type",
		"waybill_date", "current_location", "truck_number", "shipper_name", "shipper_address",
		"consignee_name", "consignee_address", "receiver_name", "receiver_contact_number",
		"container_number", "number_of_packages", "gross_weight", "volume_cbm",
		"cargo_description", "hs_code", "origin", "destination",
		"vehicle", "driver", "vehicle_plate_number", "driver_name", "driver_mobile",
		"gate_pass_number", "truck_type",
		"airline", "flight_number", "mawb_number", "hawb_number", "departure_airport", "arrival_airport",
		"shipping_line", "vessel_name", "voyage_number", "bl_number", "mbl_number", "hbl_number",
		"port_of_loading", "port_of_discharge"
	)
	out = {}
	for f in fields:
		v = getattr(wb, f, None)
		if v is not None:
			out[f] = v
	out["waybill_number"] = getattr(wb, "waybill_number", None) or wb.name
	try:
		if wb.number_of_packages is not None:
			out["number_of_packages"] = wb.number_of_packages if isinstance(wb.number_of_packages, str) else str(int(wb.number_of_packages))
	except (TypeError, ValueError):
		pass
	return out


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
		"consignee_address": job.destination or getattr(job, "delivery_address", None),
		"waybill": job.waybill_reference,
		"cargo_description": cargo_description,
		"hs_code": hs_code
	}

