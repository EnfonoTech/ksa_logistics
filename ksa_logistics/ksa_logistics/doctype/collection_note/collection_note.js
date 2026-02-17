// Helper function for float conversion
function flt(val) {
	return parseFloat(val) || 0;
}

frappe.ui.form.on('Collection Note', {
	onload: function(frm) {
		// Set job_assignment_name from route_options early, before validate runs
		if (frappe.route_options && frappe.route_options.job_assignment_name && !frm.doc.job_assignment_name) {
			frm.set_value('job_assignment_name', frappe.route_options.job_assignment_name);
		}
	},
	
	refresh: function(frm) {
		// Add link to job record
		if (frm.doc.job_record) {
			frm.add_custom_button(__('View Job Record'), function() {
				frappe.set_route("Form", "Job Record", frm.doc.job_record);
			}, __('View'));
		}
	},
	
	job_record: function(frm) {
		if (frm.doc.job_record && !frm.doc.shipper_name) {
			frappe.call({
				method: 'ksa_logistics.ksa_logistics.doctype.collection_note.collection_note.get_collection_details',
				args: { 
					job_record: frm.doc.job_record,
					job_assignment_name: frm.doc.job_assignment_name
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('customer', r.message.customer);
						frm.set_value('shipper_name', r.message.shipper_name);
						frm.set_value('collection_address', r.message.collection_address);
						// Note: total_pieces, total_weight, and total_cbm are calculated from collection_items table
						// cargo_description and hs_code come from Job Assignment (via get_collection_details)
						if (r.message.cargo_description) {
							frm.set_value('cargo_description', r.message.cargo_description);
						}
						if (r.message.hs_code) {
							frm.set_value('hs_code', r.message.hs_code);
						}
					}
				}
			});
		}
	},
	
	job_assignment_name: function(frm) {
		// Refresh cargo details when job_assignment_name changes
		if (frm.doc.job_record) {
			frm.trigger('job_record');
		}
	},
	
	collection_status: function(frm) {
		if (frm.doc.collection_status === "Completed") {
			if (!frm.doc.collection_date) {
				frm.set_value('collection_date', frappe.datetime.now_datetime());
			}
		}
	},
	
	shipper_name: function(frm) {
		if (frm.doc.shipper_name) {
			frappe.db.get_doc('Shipper', frm.doc.shipper_name).then(function(shipper) {
				if (shipper) {
					let address_str = format_shipper_address(shipper);
					frm.set_value('collection_address', address_str);
				}
			});
		} else {
			frm.set_value('collection_address', '');
		}
	}
});

frappe.ui.form.on('Collection Item', {
	quantity: function(frm, cdt, cdn) {
		calculate_cbm(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	weight: function(frm, cdt, cdn) {
		calculate_totals(frm);
	},
	
	length_cm: function(frm, cdt, cdn) {
		calculate_cbm(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	width_cm: function(frm, cdt, cdn) {
		calculate_cbm(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	height_cm: function(frm, cdt, cdn) {
		calculate_cbm(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	collection_items_remove: function(frm) {
		calculate_totals(frm);
	}
});

function format_shipper_address(shipper) {
	let parts = [];
	if (shipper.address_line1) parts.push(shipper.address_line1);
	if (shipper.address_line2) parts.push(shipper.address_line2);
	if (shipper.city) parts.push(shipper.city);
	if (shipper.state) parts.push(shipper.state);
	if (shipper.pincode) parts.push(shipper.pincode);
	if (shipper.country) parts.push(shipper.country);
	return parts.join(', ');
}

function calculate_cbm(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	if (row.length_cm && row.width_cm && row.height_cm) {
		// CBM = (L × W × H) / 1,000,000 (convert cm³ to m³)
		let cbm = (flt(row.length_cm) * flt(row.width_cm) * flt(row.height_cm)) / 1000000.0;
		// Multiply by quantity
		cbm = cbm * flt(row.quantity || 1);
		frappe.model.set_value(cdt, cdn, 'cbm', cbm);
	}
}

function calculate_totals(frm) {
	let total_pieces = 0;
	let total_weight = 0;
	let total_cbm = 0;
	
	(frm.doc.collection_items || []).forEach(row => {
		total_pieces += flt(row.quantity || 0);
		total_weight += flt(row.weight || 0);
		total_cbm += flt(row.cbm || 0);
	});
	
	frm.set_value('total_pieces', total_pieces);
	frm.set_value('total_weight', total_weight);
	frm.set_value('total_cbm', total_cbm);
}

