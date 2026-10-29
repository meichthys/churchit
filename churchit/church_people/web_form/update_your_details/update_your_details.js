// A guest cannot search people, so Shared From stays as the office set it.
frappe.ready(function () {
	for (const fieldname of ["emails", "phones"]) {
		frappe.web_form.fields_dict[fieldname].grid.update_docfield_property(
			"shared_from",
			"hidden",
			1
		);
	}
});
