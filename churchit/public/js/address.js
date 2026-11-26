// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Suggests the states of the address's country, when its country has a list (address_states.py).
// A typed code such as IL stays for the save to turn into its full name, instead of the
// Autocomplete clearing a value that is not on the list.
frappe.ui.form.on("Address", {
	refresh(frm) {
		frm.set_df_property("state", "ignore_validation", 1);
		set_state_options(frm);
	},
	country: set_state_options,
});

async function set_state_options(frm) {
	const states = frm.doc.country
		? await frappe.xcall(
				"churchit.church_people.address_states.get_state_names",
				{ country: frm.doc.country },
				"GET",
			)
		: [];
	frm.fields_dict.state.set_data(states);
}
