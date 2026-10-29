// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Church Email"] = {
	get_indicator(doc) {
		const colors = { Draft: "gray", Scheduled: "orange", Sending: "blue", Sent: "green" };
		return [__(doc.status), colors[doc.status], `status,=,${doc.status}`];
	},
};
