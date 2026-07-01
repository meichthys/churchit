// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Function Sign-Up", {
	refresh(frm) {
		// Customize the items grid: hide Description, show qty_needed, qty_signed_up, my_quantity.
		const grid = frm.fields_dict.table_iprj && frm.fields_dict.table_iprj.grid;
		if (grid) {
			grid.update_docfield_property("description", "in_list_view", 0);
			grid.update_docfield_property("description", "hidden", 1);
			grid.update_docfield_property("quantity_needed", "in_list_view", 1);
			grid.update_docfield_property("quantity_needed", "read_only", 1);
			grid.update_docfield_property("quantity_signed_up", "in_list_view", 1);
			grid.update_docfield_property("my_quantity", "in_list_view", 1);
			grid.update_docfield_property("my_quantity", "hidden", 0);
			// Force re-evaluation of which columns are visible — by default the grid
			// caches `visible_columns` and won't pick up our docfield property changes.
			//grid.reset_grid();
		}

		// Restrict the Item dropdown to items configured on the selected Function.
		// The grid button below lets the user escape the filter.
		if (frm._restrict_items === undefined) frm._restrict_items = true;

		frm.set_query("item", "table_iprj", function (doc) {
			if (!frm._restrict_items) return {};
			return {
				query: "churchit.church_ministries.doctype.function_sign_up.function_sign_up.get_function_items",
				filters: { function: doc.function },
			};
		});

		if (grid) {
			const unfilter_label = __("Unfilter Items");
			const filter_label = __("Filter Items by Function");
			const remove_grid_button = (label) => {
				if (grid.custom_buttons && grid.custom_buttons[label]) {
					grid.custom_buttons[label].remove();
					delete grid.custom_buttons[label];
				}
			};
			const render_grid_button = () => {
				remove_grid_button(unfilter_label);
				remove_grid_button(filter_label);
				const btn = grid.add_custom_button(
					frm._restrict_items ? unfilter_label : filter_label,
					() => {
						frm._restrict_items = !frm._restrict_items;
						render_grid_button();
					},
				);
				const add_row = grid.wrapper.find(".grid-add-row").first();
				if (btn && add_row.length) btn.insertAfter(add_row);
			};
			render_grid_button();
		}

		// Populate quantity_signed_up (virtual) for any rows already present.
		populate_row_totals(frm);
	},

	function(frm) {
		// When the Function changes on an existing form, refresh totals for any rows.
		populate_row_totals(frm);
	},
});

frappe.ui.form.on("Function Sign-Up Item", {
	item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item || !frm.doc.function) return;
		frappe.call({
			method:
				"churchit.church_ministries.doctype.function_sign_up.function_sign_up.get_item_status",
			args: {
				function: frm.doc.function,
				item: row.item,
			},
			callback: function (r) {
				if (!r.message) return;
				frappe.model.set_value(cdt, cdn, "quantity_needed", r.message.quantity_needed);
				frappe.model.set_value(cdt, cdn, "quantity_signed_up", r.message.quantity_signed_up);
			},
		});
	},
});

function populate_row_totals(frm) {
	if (!frm.doc.function || !(frm.doc.table_iprj || []).length) return;
	frappe.call({
		method:
			"churchit.church_ministries.doctype.function_sign_up.function_sign_up.get_function_item_totals",
		args: {
			function: frm.doc.function,
		},
		callback: function (r) {
			if (!r.message) return;
			(frm.doc.table_iprj || []).forEach((row) => {
				const data = r.message[row.item];
				if (!data) return;
				row.quantity_needed = data.quantity_needed;
				row.quantity_signed_up = data.quantity_signed_up;
			});
			frm.refresh_field("table_iprj");
		},
	});
}
