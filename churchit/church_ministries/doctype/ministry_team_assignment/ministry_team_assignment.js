// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Ministry Team Assignment", {
	setup(frm) {
		// Only the people listed on the position can be assigned to it.
		frm.set_query("person", () => ({
			filters: { name: ["in", frm.position_people || []] },
		}));
	},

	onload(frm) {
		load_position_people(frm);
	},

	position(frm) {
		load_position_people(frm);
	},
});

async function load_position_people(frm) {
	frm.position_people = [];
	if (!frm.doc.position) return;
	const position = await frappe.db.get_doc(
		"Ministry Team Position",
		frm.doc.position,
	);
	frm.position_people = (position.people || []).map((row) => row.person);
}
