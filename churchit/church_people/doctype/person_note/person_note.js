// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Person Note", {
	setup(frm) {
		frm.set_query("category", () => ({
			query: "churchit.church_people.notes.search_categories_to_add",
		}));
	},
});
