// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Church Email"] = {
	hide_name_column: true,
	hide_name_filter: true,
	formatters: {
		// A message that is not sent has reached no one yet, so 0 would mislead.
		recipients: (value, df, doc) => (doc.status === "Sent" ? value : ""),
	},
};
