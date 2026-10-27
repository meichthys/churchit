// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// An import keeps no records, so its list is the people it brought in.
frappe.listview_settings["Breeze Import"] = {
	onload() {
		frappe.set_route("List", "Person", { legacy_system: "Breeze" });
	},
};
