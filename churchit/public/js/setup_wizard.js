// Setup wizard slide for Church app. Asks the user whether to populate the
// site with sample data so they can explore the app right away.

frappe.setup.on("before_load", function () {
	// Another app's wizard (ERPNext's, say) on a site already in use must not offer sample data.
	if (frappe.boot.setup_wizard_completed_apps?.includes("frappe")) {
		return;
	}
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
					"Populate the site with a sample church, people, families, donations, prayer requests, and more so you can explore the app right away. You can remove this data later.",
				),
			},
		],
	});
});
