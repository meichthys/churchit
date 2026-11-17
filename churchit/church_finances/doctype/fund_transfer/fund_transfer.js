// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Fund Transfer", {
	setup(frm) {
		// Money stays in the church that moves it: the destination is one of its funds or a shared one
		// (FundTransfer.validate). The church follows the source fund, and a shared source keeps the user's.
		// With no source and one church there is nothing to filter, and an empty filter set
		// makes the picker say "Filtered by: ." with nothing named.
		frm.set_query("to_fund", () => {
			const filters = [];
			if (frm.doc.from_fund) filters.push(["name", "!=", frm.doc.from_fund]);
			const church_name =
				church.is_multi_church() && (frm.doc.church || frappe.boot.churchit.church);
			if (church_name) filters.push(["church", "in", [church_name, ""]]);
			return filters.length ? { filters } : {};
		});
	},

	from_fund: function (frm) {
		// Clear to_fund if it's the same as from_fund
		if (frm.doc.to_fund === frm.doc.from_fund) {
			frm.set_value("to_fund", null);
		}
	},
});
