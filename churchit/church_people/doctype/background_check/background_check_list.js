// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Background Check"] = {
	get_indicator(doc) {
		const colors = {
			Requested: "orange",
			Pending: "blue",
			Cleared: "green",
			"Not Cleared": "red",
			Expired: "gray",
		};
		return [__(doc.status), colors[doc.status], `status,=,${doc.status}`];
	},
};
