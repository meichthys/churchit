frappe.ready(function () {
	// Shared From always links to another Person here. The portal cannot run a
	// Dynamic Link, whose control needs desk boot data.
	const value_fields = { emails: "email_address", phones: "phone_number" };
	for (const [fieldname, value_field] of Object.entries(value_fields)) {
		const grid = frappe.web_form.fields_dict[fieldname].grid;
		const shared_from = {
			fieldtype: "Link",
			options: "Person",
			only_select: 1,
			get_query: (row) => ({
				query: "churchit.contacts.search_holders",
				filters: {
					child_doctype: grid.df.options,
					value: row[value_field],
					parent: frappe.web_form.doc.name,
				},
			}),
			filter_description: __("Only people who have it."),
		};
		for (const [property, value] of Object.entries(shared_from)) {
			grid.update_docfield_property("shared_from", property, value);
		}
	}

	frappe.web_form.validate = () => {
		for (const fieldname of Object.keys(value_fields)) {
			for (const row of frappe.web_form.get_value(fieldname) || []) {
				row.shared_from_type = "Person";
			}
		}
		return true;
	};
});
