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
				default: 0,
				description: __(
					"Fills the site with a made-up church, so you can try every part. Demo logins use their email address as the password. Do not use sample data on a site that people can reach from the internet. To start fresh, open Settings > Sample Data and click Delete All Data. It removes the sample records, the demo logins and every record you added."
				),
			},
		],
	});
});
