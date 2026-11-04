// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Follow-up Action Run"] = {
	hide_name_column: true,
	hide_name_filter: true,
	formatters: {
		// The desk colors a Select pill by its words, which would show every "Card Opened" in red.
		event: (value) => frappe.utils.escape_html(__(value || "")),
	},
};
