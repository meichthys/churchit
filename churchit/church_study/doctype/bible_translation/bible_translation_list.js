// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Bible Translation"] = {
	get_indicator(doc) {
		const colors = { Ready: "green", Downloading: "blue", Failed: "red", "No Text": "gray" };
		return [__(doc.status), colors[doc.status], `status,=,${doc.status}`];
	},
};
