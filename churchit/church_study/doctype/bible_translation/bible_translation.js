// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Bible Translation", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Ready") {
			frm.add_custom_button(__("Read"), () => frappe.set_route("bible", frm.doc.name));
		}
		if (frm.doc.source === "Free Use Bible API" && frm.doc.status !== "Downloading") {
			frm.add_custom_button(__("Download Again"), () =>
				frm.call("download_again").then(() => frm.reload_doc())
			);
		}
		const notes = {
			Downloading: [
				__("The text is downloading. Reload in a minute to see it ready."),
				"blue",
			],
			Failed: [__("The download failed. Check the ID, then click Download Again."), "red"],
			"No Text": [__("Attach this translation's text to read it in the app."), "orange"],
		};
		if (notes[frm.doc.status]) frm.set_intro(...notes[frm.doc.status]);
	},
});
