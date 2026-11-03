// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// A draft with an imbalance cannot be submitted, so the list tells it apart from one that can.
frappe.listview_settings["Collection"] = {
	has_indicator_for_draft: true,
	has_indicator_for_cancelled: true,
	add_fields: ["imbalance"],
	get_indicator(doc) {
		if (doc.docstatus === 2) return [__("Cancelled"), "gray", "docstatus,=,2"];
		if (doc.docstatus !== 0) return;
		if (flt(doc.imbalance)) return [__("Unbalanced"), "red", "docstatus,=,0|imbalance,!=,0"];
		return [__("Ready to Submit"), "orange", "docstatus,=,0|imbalance,=,0"];
	},
};
