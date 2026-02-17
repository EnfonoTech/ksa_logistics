#!/usr/bin/env python3
"""
Script to manually add workflow tracking columns to Job Assignment table
Run this if migration is blocked by database locks
"""

import frappe
import sys

def add_columns():
	"""Add workflow tracking columns to tabJob Assignment table"""
	
	# Connect to database
	frappe.init(site='all')
	frappe.connect()
	
	columns_to_add = [
		("collection_note", "VARCHAR(140)", "Link to Collection Note"),
		("collection_status", "VARCHAR(140)", "Collection Status"),
		("collection_date", "DATETIME(6)", "Collection Date"),
		("waybill_reference", "VARCHAR(140)", "Link to Waybill"),
		("waybill_status", "VARCHAR(140)", "Waybill Status"),
		("delivery_note_record", "VARCHAR(140)", "Link to Delivery Note Record"),
		("delivery_status", "VARCHAR(140)", "Delivery Status"),
		("pod_reference", "VARCHAR(140)", "Link to Proof of Delivery"),
		("pod_status", "VARCHAR(140)", "POD Status"),
		("document_status", "VARCHAR(140)", "Document Status"),
	]
	
	print("Adding columns to tabJob Assignment table...")
	
	for column_name, column_type, description in columns_to_add:
		try:
			# Check if column already exists
			result = frappe.db.sql(f"""
				SHOW COLUMNS FROM `tabJob Assignment` LIKE '{column_name}'
			""", as_dict=True)
			
			if result:
				print(f"  ✓ Column '{column_name}' already exists")
			else:
				# Add column
				frappe.db.sql(f"""
					ALTER TABLE `tabJob Assignment`
					ADD COLUMN `{column_name}` {column_type} NULL
				""")
				frappe.db.commit()
				print(f"  ✓ Added column '{column_name}' ({description})")
		except Exception as e:
			print(f"  ✗ Error adding column '{column_name}': {str(e)}")
	
	print("\nDone! Columns have been added to Job Assignment table.")
	print("You can now retry the migration or use the workflow features.")

if __name__ == "__main__":
	try:
		add_columns()
	except Exception as e:
		print(f"Error: {str(e)}")
		sys.exit(1)


