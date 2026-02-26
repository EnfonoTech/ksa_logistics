# -*- coding: utf-8 -*-
# Copyright (c) 2026, KSA Logistics and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import now_datetime, today


class Waybill(Document):
	def autoname(self):
		"""Generate waybill number based on transport mode"""
		if not self.transport_mode and self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			self.transport_mode = self.get_transport_mode(job.job_types)
		
		# Generate appropriate waybill number
		if self.transport_mode == "Land":
			prefix = "TWB"
		elif self.transport_mode == "Air":
			prefix = "AWB"
		elif self.transport_mode == "Sea":
			prefix = "BL"
		else:
			prefix = "WB"
		
		from frappe.model.naming import make_autoname
		self.waybill_number = make_autoname(f"{prefix}-.YY.-.MM.-.####")
	
	def get_transport_mode(self, job_type_link):
		"""Convert job type to transport mode"""
		if not job_type_link:
			return "Land"
		
		# job_type_link is a Link field, so fetch the Job Type record
		try:
			job_type_doc = frappe.get_doc("Job Type", job_type_link)
			job_type_value = job_type_doc.job_type or ""
		except:
			# Fallback to string comparison if Job Type doesn't exist
			job_type_value = str(job_type_link)
		
		job_type_str = str(job_type_value).upper()
		if "LAND" in job_type_str:
			return "Land"
		elif "AIR" in job_type_str:
			return "Air"
		elif "SEA" in job_type_str:
			return "Sea"
		return "Land"
	
	def validate(self):
		"""Validate waybill"""
		self.validate_mode_specific_fields()
		self.validate_job_record()
		self.set_defaults_from_job()
	
	def on_update(self):
		"""Actions on save/update"""
		self.update_job_record()
	
	def validate_mode_specific_fields(self):
		"""Validate required fields based on transport mode"""
		if self.transport_mode == "Land":
			if not self.vehicle:
				frappe.throw(_("Vehicle is required for Land transport"))
			if not self.driver:
				frappe.throw(_("Driver is required for Land transport"))
		
		elif self.transport_mode == "Air":
			if not self.airline:
				frappe.throw(_("Airline is required for Air transport"))
			if not self.flight_number:
				frappe.throw(_("Flight number is required for Air transport"))
		
		elif self.transport_mode == "Sea":
			if not self.shipping_line:
				frappe.throw(_("Shipping line is required for Sea transport"))
			if not self.vessel_name:
				frappe.throw(_("Vessel name is required for Sea transport"))
	
	def validate_job_record(self):
		"""Validate job record and check for duplicate waybill per assignment"""
		if not self.job_record:
			# Allow saving without Job Record when explicitly unlinked
			if getattr(self, "flags", None) and getattr(self.flags, "allow_without_job_record", False):
				return
			frappe.throw(_("Job Record is required"))
		
		# Check if waybill already exists for this job assignment
		# Multiple waybills are allowed per job, but only one per job assignment
		if self.job_assignment_name:
			# Check if waybill already exists for this specific job assignment
			existing = frappe.db.exists("Waybill", {
				"job_record": self.job_record,
				"job_assignment_name": self.job_assignment_name,
				"name": ["!=", self.name]
			})
			
			if existing:
				frappe.throw(_("Waybill already exists for this Job Assignment: {0}").format(existing))
		else:
			# Legacy: If no job_assignment_name, check if waybill exists for job (backward compatibility)
			existing = frappe.db.exists("Waybill", {
				"job_record": self.job_record,
				"job_assignment_name": ["in", ["", None]],
				"name": ["!=", self.name]
			})
			
			if existing:
				frappe.msgprint(_("Warning: Waybill already exists for this job without assignment: {0}. Consider specifying a job_assignment_name for multiple waybills.").format(existing), indicator="orange")
	
	def set_defaults_from_job(self):
		"""Auto-populate fields from job record and job assignment"""
		if self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			
			# Set customer
			if not self.customer:
				self.customer = job.customer
			
			# Set shipper/consignee from Job Record (they are now Link fields to Shipper/Consignee doctypes)
			if not self.shipper_name and job.shipper:
				# Get shipper details and format address
				shipper = frappe.get_doc("Shipper", job.shipper)
				self.shipper_name = shipper.shipper_name
				if not self.shipper_address:
					self.shipper_address = self.format_shipper_address(shipper)
			
			if not self.consignee_name and job.consignee:
				# Get consignee details and format address
				consignee = frappe.get_doc("Consignee", job.consignee)
				self.consignee_name = consignee.consignee_name
				if not self.consignee_address:
					self.consignee_address = self.format_consignee_address(consignee)
			
			# Set cargo details from Job Assignment if available, otherwise from Job Record
			# PRIORITY: Job Assignment cargo details > Job Record Package Details totals
			number_of_packages = None
			gross_weight = None
			volume_cbm = None
			cargo_description = None
			hs_code = None
			
			# FIRST: Try to get cargo details from Job Assignment if job_assignment_name is set
			# CRITICAL: Always use Job Assignment cargo details when job_assignment_name is set
			job_assignment_found = False
			if self.job_assignment_name:
				for ja in job.job_assignment:
					# Match by name (row ID) or idx (row number)
					if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
						job_assignment_found = True
						# Use Job Assignment cargo details (even if empty/None, don't fall back to Job Record totals)
						number_of_packages = ja.number_of_packages
						gross_weight = ja.gross_weight_kg
						volume_cbm = ja.volume_cbm
						cargo_description = ja.cargo_description
						hs_code = ja.hs_code
						break
			
			# FALLBACK: Only use Job Record Package Details totals if Job Assignment was NOT set or NOT found
			if not self.job_assignment_name or not job_assignment_found:
				number_of_packages = job.number_of_packagescontainer_pallets
				gross_weight = job.gross_weight_kg
				volume_cbm = job.volume_cbm
				cargo_description = job.hs_description
				hs_code = job.hs_code
			
			# Set cargo fields - ALWAYS set from Job Assignment if job_assignment_name is set AND row was found
			# This ensures Job Assignment values override any existing values (including Job Record Package Details)
			if self.job_assignment_name and job_assignment_found:
				# Force set from Job Assignment (even if None/empty, to clear any Job Record values)
				self.number_of_packages = number_of_packages
				self.gross_weight = gross_weight
				self.volume_cbm = volume_cbm
				self.cargo_description = cargo_description
				self.hs_code = hs_code
			else:
				# Only set if not already set (for Job Record fallback when no Job Assignment selected)
				if not self.number_of_packages and number_of_packages:
					self.number_of_packages = number_of_packages
				if not self.gross_weight and gross_weight:
					self.gross_weight = gross_weight
				if not self.volume_cbm and volume_cbm:
					self.volume_cbm = volume_cbm
				if not self.cargo_description and cargo_description:
					self.cargo_description = cargo_description
				if not self.hs_code and hs_code:
					self.hs_code = hs_code
			
			# Set origin/destination
			if not self.origin:
				self.origin = job.origin
			if not self.destination:
				self.destination = job.destination
			
			# Set waybill date
			if not self.waybill_date:
				self.waybill_date = job.date or today()
			
			# Shipment type from Job Record
			if not self.shipment_type and getattr(job, "shipment_type", None):
				self.shipment_type = job.shipment_type
			
			# Truck number from Job Assignment when linked
			if self.job_assignment_name:
				for ja in job.job_assignment:
					if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
						if not self.truck_number and getattr(ja, "truck_number", None):
							self.truck_number = ja.truck_number
						break
			
			# Mode-specific fields
			if self.transport_mode == "Land":
				if not self.truck_type:
					self.truck_type = job.truck_type
				if not self.gate_pass_number:
					self.gate_pass_number = job.gate_pass
			
			elif self.transport_mode == "Air":
				if not self.airline:
					self.airline = job.airline
				if not self.mawb_number:
					self.mawb_number = job.mawb
				if not self.hawb_number:
					self.hawb_number = job.hawb
				if not self.flight_number:
					self.flight_number = job.flight_no
				if not self.departure_airport:
					self.departure_airport = job.aol_airport_of_loading
				if not self.arrival_airport:
					self.arrival_airport = job.aod_airport_of_destination
			
			elif self.transport_mode == "Sea":
				if not self.shipping_line:
					self.shipping_line = job.shipping_line
				if not self.vessel_name:
					self.vessel_name = job.vessel_name
				if not self.voyage_number:
					self.voyage_number = job.voyage_no
				if not self.bl_number:
					self.bl_number = job.bl_no
				if not self.mbl_number:
					self.mbl_number = job.mbl
				if not self.hbl_number:
					self.hbl_number = job.hbl
				if not self.port_of_loading:
					self.port_of_loading = job.port_of_loadingpol
				if not self.port_of_discharge:
					self.port_of_discharge = job.port_of_dischargepod
			
	
	def format_shipper_address(self, shipper):
		"""Format shipper address object to string"""
		parts = []
		if shipper.address_line1:
			parts.append(shipper.address_line1)
		if shipper.address_line2:
			parts.append(shipper.address_line2)
		if shipper.city:
			parts.append(shipper.city)
		if shipper.state:
			parts.append(shipper.state)
		if shipper.pincode:
			parts.append(shipper.pincode)
		if shipper.country:
			parts.append(shipper.country)
		return "\n".join(parts)
	
	def format_consignee_address(self, consignee):
		"""Format consignee address object to string"""
		parts = []
		if consignee.address_line1:
			parts.append(consignee.address_line1)
		if consignee.address_line2:
			parts.append(consignee.address_line2)
		if consignee.city:
			parts.append(consignee.city)
		if consignee.state:
			parts.append(consignee.state)
		if consignee.pincode:
			parts.append(consignee.pincode)
		if consignee.country:
			parts.append(consignee.country)
		return "\n".join(parts)
	
	def update_job_record(self):
		"""Update job assignment (and optionally job record) with waybill reference"""
		if self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			
			# Update Job Assignment if job_assignment_name is provided
			if self.job_assignment_name:
				job_assignment_found = False
				for ja in job.job_assignment:
					if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
						job_assignment_found = True
						# Determine document status based on waybill status
						doc_status = "Waybill Created"
						if self.waybill_status == "In Transit":
							doc_status = "In Transit"
						elif self.waybill_status == "Arrived at Destination":
							doc_status = "Arrived"
						elif self.waybill_status == "Delivered":
							doc_status = "Delivered"
						
						# Update the Job Assignment row
						frappe.db.set_value("Job Assignment", ja.name, {
							"waybill_reference": self.name,
							"waybill_status": self.waybill_status or "Prepared",
							"document_status": doc_status
						}, update_modified=False)
						break
				
				if not job_assignment_found:
					frappe.msgprint(_("Job Assignment {0} not found in Job Record").format(self.job_assignment_name), indicator="orange")
			
			# Also update Job Record for backward compatibility (aggregate view)
			# This is optional - can be removed if not needed
			update_data = {
				"waybill_reference": self.name,
				"waybill_number": self.waybill_number,
				"waybill_status": self.waybill_status or "Prepared",
				"actual_dispatch_date": self.actual_dispatch_date or now_datetime()
			}
			
			# Update document status based on waybill status
			if self.waybill_status == "Dispatched":
				update_data["document_status"] = "Waybill Created"
			elif self.waybill_status == "In Transit":
				update_data["document_status"] = "In Transit"
			elif self.waybill_status == "Arrived at Destination":
				update_data["document_status"] = "Arrived"
			elif self.waybill_status == "Delivered":
				update_data["document_status"] = "Delivered"
			
			job.db_set(update_data, update_modified=False)

@frappe.whitelist()
def update_waybill_status(waybill_name, status, location=None, remarks=None):
	"""Update waybill status - can be called from mobile"""
	waybill = frappe.get_doc("Waybill", waybill_name)
	
	waybill.waybill_status = status
	if location:
		waybill.current_location = location
	
	# Add tracking entry
	waybill.append("tracking_history", {
		"timestamp": now_datetime(),
		"status": status,
		"location": location or waybill.current_location,
		"remarks": remarks or "",
		"updated_by": frappe.session.user
	})
	
	waybill.save()
	
	# Update job record
	job = frappe.get_doc("Job Record", waybill.job_record)
	job.db_set("waybill_status", status, update_modified=False)
	
	if status == "Delivered":
		job.db_set({
			"actual_arrival_date": now_datetime(),
			"delivery_status": "Delivered",
			"document_status": "Delivered"
		}, update_modified=False)
	
	return {"success": True, "message": _("Status updated")}

@frappe.whitelist()
def get_waybill_template(job_record, job_assignment_name=None):
	"""Get template data from job record and job assignment"""
	job = frappe.get_doc("Job Record", job_record)
	
	# Determine transport mode from Job Type Link field
	transport_mode = "Land"
	if job.job_types:
		try:
			job_type_doc = frappe.get_doc("Job Type", job.job_types)
			job_type_value = job_type_doc.job_type or ""
		except:
			job_type_value = str(job.job_types)
		
		job_type_str = str(job_type_value).upper()
		if "AIR" in job_type_str:
			transport_mode = "Air"
		elif "SEA" in job_type_str:
			transport_mode = "Sea"
	
	# Get cargo details from job assignment if provided, otherwise from job record
	# PRIORITY: Job Assignment cargo details > Job Record Package Details totals
	number_of_packages = None
	gross_weight = None
	volume_cbm = None
	cargo_description = None
	hs_code = None
	
	truck_number = None
	if job_assignment_name:
		# Find the job assignment row
		for ja in job.job_assignment:
			if str(ja.name) == str(job_assignment_name) or str(ja.idx) == str(job_assignment_name):
				# Use cargo details from job assignment (even if empty)
				number_of_packages = ja.number_of_packages
				gross_weight = ja.gross_weight_kg
				volume_cbm = ja.volume_cbm
				cargo_description = ja.cargo_description
				hs_code = ja.hs_code
				truck_number = getattr(ja, "truck_number", None)
				break
	
	# FALLBACK: Only use Job Record Package Details totals if Job Assignment not found or not set
	if number_of_packages is None:
		number_of_packages = job.number_of_packagescontainer_pallets
	if gross_weight is None:
		gross_weight = job.gross_weight_kg
	if volume_cbm is None:
		volume_cbm = job.volume_cbm
	if cargo_description is None:
		cargo_description = job.hs_description
	if hs_code is None:
		hs_code = job.hs_code
	
	# Get shipper and consignee details
	shipper_name = None
	shipper_address = None
	consignee_name = None
	consignee_address = None
	receiver_name = None
	receiver_contact_number = None
	
	if job.shipper:
		shipper = frappe.get_doc("Shipper", job.shipper)
		shipper_name = shipper.shipper_name
		shipper_address = format_shipper_address_helper(shipper)
	
	if job.consignee:
		consignee = frappe.get_doc("Consignee", job.consignee)
		consignee_name = consignee.consignee_name
		consignee_address = format_consignee_address_helper(consignee)
	
	# Receiver details come directly from Job Record (General section)
	if getattr(job, "receiver_name", None):
		receiver_name = job.receiver_name
	if getattr(job, "receiver_contact_number", None):
		receiver_contact_number = job.receiver_contact_number
	
	# Mode-specific transport details from Job Record
	air_fields = {}
	sea_fields = {}

	if transport_mode == "Air":
		air_fields = {
			"airline": job.airline,
			"flight_number": job.flight_no,
			"mawb_number": job.mawb,
			"hawb_number": job.hawb,
			"departure_airport": job.aol_airport_of_loading,
			"arrival_airport": job.aod_airport_of_destination,
		}
	elif transport_mode == "Sea":
		sea_fields = {
			"shipping_line": job.shipping_line,
			"vessel_name": job.vessel_name,
			"voyage_number": job.voyage_no,
			"bl_number": job.bl_no,
			"mbl_number": job.mbl,
			"hbl_number": job.hbl,
			"port_of_loading": job.port_of_loadingpol,
			"port_of_discharge": job.port_of_dischargepod,
		}

	shipment_type = getattr(job, "shipment_type", None)

	base = {
		"job_record": job.name,
		"transport_mode": transport_mode,
		"shipment_type": shipment_type,
		"customer": job.customer,
		"shipper_name": shipper_name,
		"shipper_address": shipper_address,
		"consignee_name": consignee_name,
		"consignee_address": consignee_address,
		"receiver_name": receiver_name,
		"receiver_contact_number": receiver_contact_number,
		"origin": job.origin,
		"destination": job.destination,
		"number_of_packages": number_of_packages,
		"gross_weight": gross_weight,
		"volume_cbm": volume_cbm,
		"cargo_description": cargo_description,
		"hs_code": hs_code,
		"waybill_date": job.date or today(),
		"truck_number": truck_number,
	}

	# Merge base with mode-specific fields (later keys override)
	return {**base, **air_fields, **sea_fields}

def format_shipper_address_helper(shipper):
	"""Helper function to format shipper address"""
	if not shipper:
		return None
	parts = []
	if shipper.address_line1:
		parts.append(shipper.address_line1)
	if shipper.address_line2:
		parts.append(shipper.address_line2)
	if shipper.city:
		parts.append(shipper.city)
	if shipper.state:
		parts.append(shipper.state)
	if shipper.pincode:
		parts.append(shipper.pincode)
	if shipper.country:
		parts.append(shipper.country)
	return "\n".join(parts) if parts else None

def format_consignee_address_helper(consignee):
	"""Helper function to format consignee address"""
	if not consignee:
		return None
	parts = []
	if consignee.address_line1:
		parts.append(consignee.address_line1)
	if consignee.address_line2:
		parts.append(consignee.address_line2)
	if consignee.city:
		parts.append(consignee.city)
	if consignee.state:
		parts.append(consignee.state)
	if consignee.pincode:
		parts.append(consignee.pincode)
	if consignee.country:
		parts.append(consignee.country)
	return "\n".join(parts) if parts else None


@frappe.whitelist()
def unlink_from_job_record(waybill_name: str):
	"""Unlink this Waybill from its Job Record and related Job Assignment / vouchers."""
	if not waybill_name:
		return

	waybill = frappe.get_doc("Waybill", waybill_name)

	if not waybill.job_record:
		return {"success": True}

	job = frappe.get_doc("Job Record", waybill.job_record)

	# Clear references on Job Assignment rows so vouchers2 sync will stop recreating
	for ja in (job.job_assignment or []):
		if ja.waybill_reference == waybill.name:
			ja.waybill_reference = None
			ja.waybill_status = None

	# Also clear top-level Job Record waybill reference if it matches
	if getattr(job, "waybill_reference", None) == waybill.name:
		job.waybill_reference = None
		job.waybill_status = None

	job.save(ignore_permissions=True)

	# Unlink from Waybill side (keep data like cargo, receiver, etc.)
	waybill.job_record = None
	waybill.job_assignment_name = None
	# Set flag so validate_job_record allows saving without job_record
	waybill.flags.allow_without_job_record = True
	waybill.save(ignore_permissions=True)

	# Resync vouchers table to drop any auto-added workflow voucher rows
	try:
		from ksa_logistics.ksa_logistics.doctype.job_record.job_record import sync_workflow_vouchers
		sync_workflow_vouchers(job.name)
	except Exception:
		# Fail-safe: don't block unlinking if sync fails
		frappe.log_error(frappe.get_traceback(), "Waybill unlink_from_job_record sync error")

	return {"success": True}

