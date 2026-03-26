// Setup wizard customizations for the Church app.
//
// 1. Relabels ERPNext's "Company" fields to "Church" on the organization slide.
// 2. Adds a slide asking whether to populate the site with sample data.

frappe.setup.on("before_load", function () {
	// --- Relabel ERPNext organization slide fields ---
	const org_slide = erpnext.setup.slides_settings.find((s) => s.name === "organization");
	if (org_slide) {
		org_slide.title = __("Setup your church");
		for (const field of org_slide.fields) {
			if (field.fieldname === "company_name") {
				field.label = __("Church Name");
			} else if (field.fieldname === "company_abbr") {
				field.label = __("Church Abbreviation");
			} else if (field.fieldname === "chart_of_accounts") {
				field.hidden = 1;
			} else if (field.fieldname === "view_coa") {
				field.hidden = 1;
			} else if (field.fieldname === "setup_demo") {
				field.hidden = 1;
				field.default = 0;
			}
		}
	}

	// --- Sample data slide ---
	frappe.setup.add_slide({
		name: "church_sample_data",
		title: __("Sample Data"),
		icon: "fa fa-database",
		fields: [
			{
				fieldname: "create_sample_data",
				label: __("Create Sample Data"),
				fieldtype: "Check",
				default: 1,
				description: __(
					"Populate the site with a sample church, people, families, " +
					"donations, prayer requests, and more so you can explore " +
					"the app right away. You can remove this data later."
				),
			},
		],
	});
});
