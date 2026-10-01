// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Family"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Rolodex"), () => {
			frappe.route_options = { view: "households" };
			frappe.set_route("rolodex");
		});
	},
};
