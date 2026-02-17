frappe.ui.form.on('Proof of Delivery', {
	refresh: function(frm) {
		// Add link to job record
		if (frm.doc.job_record) {
			frm.add_custom_button(__('View Job Record'), function() {
				frappe.set_route("Form", "Job Record", frm.doc.job_record);
			}, __('View'));
		}
		
		// Add verify button
		if (frm.doc.pod_status === "Submitted") {
			frm.add_custom_button(__('Verify POD'), function() {
				verify_pod_dialog(frm);
			}, __('Actions'));
			
			frm.add_custom_button(__('Reject POD'), function() {
				reject_pod_dialog(frm);
			}, __('Actions'));
		}
		
		// Show status indicator
		if (frm.doc.pod_status === "Verified") {
			frm.dashboard.set_headline_alert(__('POD Verified'), 'green');
		} else if (frm.doc.pod_status === "Rejected") {
			frm.dashboard.set_headline_alert(__('POD Rejected'), 'red');
		}
		
		// Highlight discrepancies
		if (frm.doc.discrepancy && frm.doc.discrepancy !== 0) {
			frm.dashboard.add_indicator(__('Package Discrepancy: ' + frm.doc.discrepancy), 'red');
		}
		
		// Set job_assignment_name from route_options if available
		if (frappe.route_options && frappe.route_options.job_assignment_name && !frm.doc.job_assignment_name) {
			frm.set_value('job_assignment_name', frappe.route_options.job_assignment_name);
		}
		
		// Get job_assignment_name from delivery note or waybill if not set
		if (!frm.doc.job_assignment_name) {
			if (frm.doc.delivery_note) {
				frappe.db.get_value('Delivery Note Record', frm.doc.delivery_note, 'job_assignment_name', function(r) {
					if (r && r.job_assignment_name) {
						frm.set_value('job_assignment_name', r.job_assignment_name);
					} else if (frm.doc.waybill) {
						frappe.db.get_value('Waybill', frm.doc.waybill, 'job_assignment_name', function(r2) {
							if (r2 && r2.job_assignment_name) {
								frm.set_value('job_assignment_name', r2.job_assignment_name);
							}
						});
					}
				});
			} else if (frm.doc.waybill) {
				frappe.db.get_value('Waybill', frm.doc.waybill, 'job_assignment_name', function(r) {
					if (r && r.job_assignment_name) {
						frm.set_value('job_assignment_name', r.job_assignment_name);
					}
				});
			}
		}
	},
	
	job_record: function(frm) {
		if (frm.doc.job_record && !frm.doc.receiver_name) {
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Job Record',
					name: frm.doc.job_record,
					fields: ['number_of_packagescontainer_pallets', 'gross_weight_kg', 'job_assignment', 'delivery_note_record', 'waybill_reference']
				},
				callback: function(r) {
					if (r.message) {
						// PRIMARY: Get cargo from Job Assignment
						// FALLBACK: Use Job Record values
						let expected_packages = r.message.number_of_packagescontainer_pallets;
						let expected_weight = r.message.gross_weight_kg;
						let delivery_note = r.message.delivery_note_record;
						let waybill = r.message.waybill_reference;
						
						if (frm.doc.job_assignment_name && r.message.job_assignment) {
							let ja = r.message.job_assignment.find(j => 
								j.name === frm.doc.job_assignment_name || j.idx == frm.doc.job_assignment_name
							);
							
							if (ja) {
								// Get from Job Assignment
								expected_packages = ja.number_of_packages || expected_packages;
								expected_weight = ja.gross_weight_kg || expected_weight;
								delivery_note = ja.delivery_note_record || delivery_note;
								waybill = ja.waybill_reference || waybill;
							}
						}
						
						// Set expected values
						if (expected_packages && !frm.doc.expected_packages) {
							frm.set_value('expected_packages', expected_packages);
						}
						if (expected_weight && !frm.doc.expected_weight) {
							frm.set_value('expected_weight', expected_weight);
						}
						
						// Auto-populate delivery_note and waybill if not already set
						if (delivery_note && !frm.doc.delivery_note) {
							frm.set_value('delivery_note', delivery_note);
						}
						if (waybill && !frm.doc.waybill) {
							frm.set_value('waybill', waybill);
						}
					}
				}
			});
		}
	},
	
	job_assignment_name: function(frm) {
		// When job_assignment_name changes, refresh delivery_note and waybill
		if (frm.doc.job_record && frm.doc.job_assignment_name) {
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Job Record',
					name: frm.doc.job_record,
					fields: ['job_assignment']
				},
				callback: function(r) {
					if (r.message && r.message.job_assignment) {
						let ja = r.message.job_assignment.find(j => 
							j.name === frm.doc.job_assignment_name || j.idx == frm.doc.job_assignment_name
						);
						
						if (ja) {
							// Update delivery_note and waybill from Job Assignment
							if (ja.delivery_note_record && !frm.doc.delivery_note) {
								frm.set_value('delivery_note', ja.delivery_note_record);
							}
							if (ja.waybill_reference && !frm.doc.waybill) {
								frm.set_value('waybill', ja.waybill_reference);
							}
						}
					}
				}
			});
		}
	},
	
	delivered_packages: function(frm) {
		calculate_discrepancy(frm);
	},
	
	expected_packages: function(frm) {
		calculate_discrepancy(frm);
	},
	
	delivered_weight: function(frm) {
		calculate_weight_variance(frm);
	},
	
	cargo_condition: function(frm) {
		if (frm.doc.cargo_condition !== 'Good') {
			frm.set_df_property('damage_details', 'reqd', 1);
		} else {
			frm.set_df_property('damage_details', 'reqd', 0);
		}
	}
});

function calculate_discrepancy(frm) {
	if (frm.doc.expected_packages && frm.doc.delivered_packages) {
		let disc = frm.doc.expected_packages - frm.doc.delivered_packages;
		frm.set_value('discrepancy', disc);
		
		if (disc !== 0) {
			frappe.msgprint(__('Discrepancy detected! Please provide remarks.'));
		}
	}
}

function calculate_weight_variance(frm) {
	if (frm.doc.expected_weight && frm.doc.delivered_weight) {
		let variance = frm.doc.expected_weight - frm.doc.delivered_weight;
		frm.set_value('weight_variance', variance);
	}
}

function verify_pod_dialog(frm) {
	frappe.confirm(
		__('Are you sure you want to verify this POD? This will mark the job as completed.'),
		function() {
			frappe.call({
				method: 'ksa_logistics.ksa_logistics.doctype.proof_of_delivery.proof_of_delivery.verify_pod',
				args: { pod_name: frm.doc.name },
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'green'
						});
						frm.reload_doc();
					}
				}
			});
		}
	);
}

function reject_pod_dialog(frm) {
	frappe.prompt([
		{
			fieldname: 'reason',
			fieldtype: 'Small Text',
			label: 'Rejection Reason',
			reqd: 1
		}
	], function(values) {
		frappe.call({
			method: 'ksa_logistics.ksa_logistics.doctype.proof_of_delivery.proof_of_delivery.reject_pod',
			args: {
				pod_name: frm.doc.name,
				reason: values.reason
			},
			callback: function(r) {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: r.message.message,
						indicator: 'orange'
					});
					frm.reload_doc();
				}
			}
		});
	}, __('Reject POD'));
}

