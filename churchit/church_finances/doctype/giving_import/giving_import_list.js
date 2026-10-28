// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// An import keeps no records, so its list is the Collections it made.
frappe.listview_settings["Giving Import"] = {
	// In refresh, after the import list has used the route options, so the target list gets the filter.
	refresh() {
		frappe.route_flags.replace_route = true;
		frappe.set_route("List", "Collection", { import_batch: ["is", "set"] });
	},
};
