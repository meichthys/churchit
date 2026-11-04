// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.treeview_settings["Church Location"] = {
	// Frappe's own root is the one top location, labeled by its ID; this root lists every top location by name.
	get_tree_root: false,
	root_label: __("All Locations"),
	onload(treeview) {
		treeview.root_value = "";
		treeview.make_tree();
	},
};
