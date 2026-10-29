// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Push Settings", {
	refresh(frm) {
		if (!frm.doc.vapid_public_key) {
			frm.add_custom_button(__("Generate Keys"), () => generate_keys(frm));
		}
	},
});

function generate_keys(frm) {
	if (!frm.is_dirty()) return make_keys(frm);

	// A Single never saved opens unsaved, and the settings refuse Enabled until the keys exist.
	frm.set_value("enabled", 0)
		.then(() => frm.save())
		.then(() => !frm.is_dirty() && make_keys(frm));
}

function make_keys(frm) {
	frappe.call({
		method: "churchit.church_communications.doctype.push_settings.push_settings.generate_keys",
		freeze: true,
		callback: () => frm.reload_doc(),
	});
}
