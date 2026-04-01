// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt


frappe.ui.form.on('Function', {
	before_save(frm) {
		// Update Attendance Total when saving
		// Only include the number of 'Confirmed' and 'Assumed' attendees
		var total_attendance = 0;
		frm.doc.attendance.forEach(function (row) {
			var type = (row.attendance_type || "").replace(/^.*? - /, "");
			if (["Confirmed", "Assumed"].includes(type)) {
				total_attendance += 1;
			}
		});
		frm.set_value('attendance_total', total_attendance);
	},

	onload(frm) {
		church.set_church_doctype_query(frm, 'association_type', 'associations');
	},

	refresh: function(frm) {
		// Add template-fill functionality if we have a template specified and this is a new form
		if (!frm.is_new() || !frm.doc.type) return;
		// Check if the selected type has a template
		frappe.db.get_value('Function Type', frm.doc.type, 'template_function').then(r => {
			if (!r.message?.template_function) return;
			// Add 	Fill from Template` button if template exists
			frm.add_custom_button(__('Fill from Template'), function() {
				frappe.call({
					method: 'church.ministries.doctype.function.function.apply_template',
					args: {
						source_name: r.message.template_function,
						target_doc: frm.doc
					},
					callback: function(r) {
						if (!r.message) return;
						Object.keys(r.message).forEach(fieldname => {
							frm.set_value(fieldname, r.message[fieldname]);
						});

						frappe.msgprint({
							message: __('Template applied successfully'),
							indicator: 'green',
							alert: true
						});
					}
				});
			});
		});
	},

	type: function(frm) {
		// Refresh form to re-evaluate button visibility
		frm.trigger('refresh');
	}
});
