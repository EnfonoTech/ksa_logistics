"""
Migration script to convert Data fields back to Link fields
Run this after all doctypes have been migrated.

Usage:
bench --site your-site console
Then run: exec(open('apps/ksa_logistics/ksa_logistics/ksa_logistics/doctype/job_record/migrate_link_fields.py').read())
"""

import frappe

def migrate_link_fields():
	"""Convert Data fields back to Link fields after doctypes are created"""
	
	# Get Job Record doctype
	doc_type = frappe.get_doc("DocType", "Job Record")
	
	# Update collection_note field
	for field in doc_type.fields:
		if field.fieldname == "collection_note":
			field.fieldtype = "Link"
			field.options = "Collection Note"
			break
	
	# Update waybill_reference field
	for field in doc_type.fields:
		if field.fieldname == "waybill_reference":
			field.fieldtype = "Link"
			field.options = "Waybill"
			break
	
	# Update delivery_note_record field
	for field in doc_type.fields:
		if field.fieldname == "delivery_note_record":
			field.fieldtype = "Link"
			field.options = "Delivery Note Record"
			break
	
	# Update pod_reference field
	for field in doc_type.fields:
		if field.fieldname == "pod_reference":
			field.fieldtype = "Link"
			field.options = "Proof of Delivery"
			break
	
	doc_type.save()
	frappe.db.commit()
	print("Link fields migrated successfully!")

if __name__ == "__main__":
	migrate_link_fields()

