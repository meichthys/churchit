// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Possible Duplicate"] = {
	get_indicator(doc) {
		const colors = { Open: "orange", Merged: "green", "Not a Duplicate": "gray" };
		return [__(doc.status), colors[doc.status], `status,=,${doc.status}`];
	},
};
