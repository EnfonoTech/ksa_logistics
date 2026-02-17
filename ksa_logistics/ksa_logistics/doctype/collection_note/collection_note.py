# -*- coding: utf-8 -*-
# Copyright (c) 2026, KSA Logistics and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import now_datetime


class CollectionNote(Document):
	def validate(self):
		"""Validate collection note"""
		self.validate_job_record()
		self.calculate_totals()
		self.set_defaults_from_job()
	
	def on_update(self):
		"""Actions on save/update"""
		# Only update if document is being saved (not just loaded)
		if not self.flags.ignore_update_job_record:
			self.update_job_record()
	
	def validate_job_record(self):
		"""Validate job record and job assignment"""
		if not self.job_record:
			frappe.throw(_("Job Record is required"))
		
		# If job_assignment_name is provided, check if collection note already exists for this assignment
		if self.job_assignment_name:
			job = frappe.get_doc("Job Record", self.job_record)
			job_assignment_found = False
			existing_collection_note = None
			
			# Find the job assignment row in the loaded document
			for ja in job.job_assignment:
				if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
					job_assignment_found = True
					# Try to get collection_note from the child table row
					# Use getattr to safely access the field (it might not be loaded)
					existing_collection_note = getattr(ja, 'collection_note', None)
					break
			
			if not job_assignment_found:
				frappe.throw(_("Job Assignment {0} not found in Job Record").format(self.job_assignment_name))
			
			# If collection_note wasn't found in the loaded document, try querying the database
			# But handle the case where the column might not exist yet (migration not run)
			if existing_collection_note is None:
				try:
					# Check if column exists first by querying table structure
					columns = frappe.db.sql("""
						SHOW COLUMNS FROM `tabJob Assignment` LIKE 'collection_note'
					""", as_dict=True)
					
					if columns:
						# Column exists, so we can query it
						result = frappe.db.sql("""
							SELECT collection_note
							FROM `tabJob Assignment` 
							WHERE parent = %s 
							AND (name = %s OR idx = %s)
							LIMIT 1
						""", (self.job_record, self.job_assignment_name, self.job_assignment_name), as_dict=True)
						
						if result:
							existing_collection_note = result[0].get('collection_note')
				except Exception:
					# Column doesn't exist yet - this is OK, migration will add it
					# Skip the duplicate check for now
					existing_collection_note = None
			
			# Check if collection note already exists for this assignment
			if existing_collection_note and existing_collection_note != self.name:
				frappe.throw(_("Collection Note already exists for this Job Assignment: {0}").format(existing_collection_note))
		else:
			# Legacy: Check if collection note already exists for this job (without assignment)
			existing = frappe.db.exists("Collection Note", {
				"job_record": self.job_record,
				"job_assignment_name": ["in", ["", None]],
				"name": ["!=", self.name]
			})
			
			if existing:
				frappe.msgprint(_("Warning: Collection Note already exists for this job without assignment: {0}").format(existing), indicator="orange")
	
	def calculate_totals(self):
		"""Calculate totals including CBM"""
		total_pieces = 0
		total_weight = 0.0
		total_cbm = 0.0
		
		for item in self.collection_items:
			total_pieces += item.quantity or 0
			total_weight += item.weight or 0
			# Calculate CBM for this item if dimensions are provided
			if item.length_cm and item.width_cm and item.height_cm:
				# CBM = (L × W × H) / 1,000,000 (convert cm³ to m³)
				item_cbm = (item.length_cm * item.width_cm * item.height_cm) / 1000000.0
				# Multiply by quantity
				item_cbm = item_cbm * (item.quantity or 1)
				item.cbm = item_cbm
				total_cbm += item_cbm
			elif item.cbm:
				# Use manually entered CBM
				total_cbm += item.cbm * (item.quantity or 1)
		
		self.total_pieces = total_pieces
		self.total_weight = total_weight
		self.total_cbm = total_cbm
	
	def set_defaults_from_job(self):
		"""Auto-populate fields from job record and job assignment"""
		if self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			
			# Set customer
			if not self.customer:
				self.customer = job.customer
			
			# Set shipper from Job Record (now Link to Shipper doctype)
			if not self.shipper_name and job.shipper:
				shipper = frappe.get_doc("Shipper", job.shipper)
				self.shipper_name = shipper.shipper_name
			
			# Set collection address
			if not self.collection_address:
				self.collection_address = job.origin or job.pickup_point
			
			# Set cargo details - PRIORITY: Job Assignment > Job Record Package Details
			# Initialize with None
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
	
	def update_job_record(self):
		"""Update job assignment (and optionally job record) with collection note reference"""
		if self.job_record:
			job = frappe.get_doc("Job Record", self.job_record)
			
			# Update Job Assignment if job_assignment_name is provided
			if self.job_assignment_name:
				job_assignment_found = False
				job_assignment_row_name = None
				doc_status = "Collection Completed" if self.collection_status == "Completed" else "Collection Scheduled"
				
				# Find the Job Assignment row
				for ja in job.job_assignment:
					if str(ja.name) == str(self.job_assignment_name) or str(ja.idx) == str(self.job_assignment_name):
						job_assignment_found = True
						job_assignment_row_name = ja.name
						
						# Update the child table row using setattr (works even if field doesn't exist in DB yet)
						setattr(ja, 'collection_note', self.name)
						setattr(ja, 'collection_status', self.collection_status)
						setattr(ja, 'document_status', doc_status)
						if self.collection_date:
							setattr(ja, 'collection_date', self.collection_date)
						
						break
				
				if job_assignment_found and job_assignment_row_name:
					# Try SQL UPDATE first (if columns exist)
					try:
						frappe.db.sql("""
							UPDATE `tabJob Assignment`
							SET collection_note = %s,
								collection_status = %s,
								document_status = %s,
								collection_date = %s
							WHERE parent = %s AND name = %s
						""", (
							self.name,
							self.collection_status,
							doc_status,
							self.collection_date or now_datetime(),
							self.job_record,
							job_assignment_row_name
						))
						frappe.db.commit()
					except Exception:
						# Columns don't exist yet - update through document save
						# This stores the values in the document, and they'll be saved to DB after migration
						try:
							job.flags.ignore_validate = True
							job.flags.ignore_links = True
							job.save(ignore_permissions=True, ignore_validate=True)
							frappe.db.commit()
						except Exception as e:
							# If save fails, at least the values are set in memory
							# They'll be persisted when migration runs and document is saved again
							frappe.log_error(f"Could not update Job Assignment: {str(e)}", "Collection Note Update")
				else:
					frappe.msgprint(_("Job Assignment {0} not found in Job Record").format(self.job_assignment_name), indicator="orange")
			
			# Also update Job Record with collection note reference
			# This provides an aggregate view of the latest collection note
			job.db_set({
				"collection_note": self.name,
				"collection_status": self.collection_status,
				"collection_date": self.collection_date or now_datetime()
			}, update_modified=False)
			
			# Also update Job Record for backward compatibility (aggregate view)
			# Check if all assignments have collection notes completed
			# But first check if the column exists
			try:
				columns = frappe.db.sql("""
					SHOW COLUMNS FROM `tabJob Assignment` LIKE 'collection_status'
				""", as_dict=True)
				
				if columns:
					# Column exists, so we can query it
					result = frappe.db.sql("""
						SELECT 
							COUNT(*) as total,
							SUM(CASE WHEN collection_status = 'Completed' THEN 1 ELSE 0 END) as completed
						FROM `tabJob Assignment`
						WHERE parent = %s
					""", (self.job_record,), as_dict=True)
					
					if result:
						total_count = result[0].get('total', 0)
						completed_count = result[0].get('completed', 0)
						
						if total_count > 0 and completed_count == total_count:
							job.db_set({
								"collection_status": "Completed",
								"collection_date": self.collection_date or now_datetime()
							}, update_modified=False)
						elif self.collection_status == "Completed":
							job.db_set("collection_status", "In Progress", update_modified=False)
			except Exception:
				# Column doesn't exist yet - skip this check
				pass

@frappe.whitelist()
def get_collection_details(job_record, job_assignment_name=None):
	"""Get collection details from job and job assignment"""
	job = frappe.get_doc("Job Record", job_record)
	
	# Get shipper details
	shipper_name = None
	if job.shipper:
		shipper = frappe.get_doc("Shipper", job.shipper)
		shipper_name = shipper.shipper_name
	
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
		"shipper_name": shipper_name,
		"collection_address": job.origin or job.pickup_point,
		# Note: total_pieces, total_weight, and total_cbm are calculated from collection_items table
		# cargo_description and hs_code come from Job Assignment if available
		"cargo_description": cargo_description,
		"hs_code": hs_code
	}

