// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Authorized Pickup", {
	setup(frm) {
		// The household's Adults may always collect its children, and a child collects no one.
		frm.set_query("person", () => ({
			filters: { name: ["not in", frm.household || []] },
		}));
	},
	refresh(frm) {
		frm.trigger("family");
	},
	family(frm) {
		frm.household = [];
		if (!frm.doc.family) return;
		frappe.db.get_doc("Family", frm.doc.family).then((family) => {
			frm.household = (family.members || [])
				.filter((row) => ["Adult", "Child"].includes(row.household_role))
				.map((row) => row.member);
		});
	},
});
