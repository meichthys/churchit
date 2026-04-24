// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt


frappe.ui.form.on('Function', {
	onload(frm) {
		church.set_church_doctype_query(frm, 'association_type', 'associations');
	},

	refresh: function(frm) {
		// Add template-fill functionality if we have a template specified and this is a new form
		if (frm.is_new() && frm.doc.type) {
			frappe.db.get_value('Function Type', frm.doc.type, 'template_function').then(r => {
				if (!r.message?.template_function) return;
				// Add 	Fill from Template` button if template exists
				frm.add_custom_button(__('Fill from Template'), function() {
					frappe.call({
						method: 'church.church_ministries.doctype.function.function.apply_template',
						args: {
							source_name: r.message.template_function,
							target_doc: frm.doc
						},
						callback: function(r) {
							if (!r.message) return;
							Object.keys(r.message).forEach(fieldname => {
								frm.set_value(fieldname, r.message[fieldname]);
							});

							// Fetch link titles for person IDs so the attendance grid
							// displays names instead of IDs (e.g. "John Smith" not "PRSN-0011")
							const personIds = [...new Set(
								(r.message.attendance || []).map(a => a.person).filter(Boolean)
							)];
							if (personIds.length) {
								Promise.all(personIds.map(id => frappe.utils.fetch_link_title('Person', id)))
									.then(() => frm.refresh_field('attendance'));
							}

							frappe.msgprint({
								message: __('Template applied successfully'),
								indicator: 'green',
								alert: true
							});
						}
					});
				});
			});
		}

		// Add Sign Ups buttons if sign-ups are enabled, there are items, or there are linked sign-ups
		if (!frm.is_new()) {
			const has_items = frm.doc.table_cxhh && frm.doc.table_cxhh.length > 0;

			frappe.db.count('Function Sign-Up', {
				filters: { function: frm.doc.name }
			}).then(count => {
				if (frm.doc.allow_sign_ups || has_items || count > 0) {
					frm.add_custom_button(__('Show Signed-Up Items'), function() {
						frappe.set_route('query-report', 'Function Sign-Up Items', {
							function: frm.doc.name
						});
					}, __('Sign Ups'));

					frm.add_custom_button(__('Show Signed-Up People'), function() {
						frappe.set_route('list', 'Function Sign-Up', {
							function: frm.doc.name
						});
					}, __('Sign Ups'));
				}
			});
		}
	},


	type: function(frm) {
		// Refresh form to re-evaluate button visibility
		frm.trigger('refresh');
	},

	after_save: function(frm) {
		// Sync item quantities after saving
		if (!frm.is_new()) {
			frappe.call({
				method: "church.church_ministries.doctype.function_sign_up.function_sign_up.sync_item_quantities_for_function",
				args: {
					function: frm.doc.name,
				},
			});
		}
	}
});

// Set default attendance_type on new attendance child rows
frappe.ui.form.on('Function Attendance', {
	attendance_add(frm, cdt, cdn) {
		frappe.db.get_value("Function Attendance Type", { type: "Confirmed" }, "name").then(r => {
			if (r.message?.name) {
				frappe.model.set_value(cdt, cdn, "attendance_type", r.message.name);
			}
		});
	}
});
