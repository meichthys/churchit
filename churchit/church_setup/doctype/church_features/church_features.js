// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Church Features", {
	after_save(frm) {
		// The sidebar, app switcher and workspace list all come from the cached
		// bootinfo, so the desk keeps showing the old set until it is reloaded.
		frappe.confirm(
			__("Module visibility has changed. Reload now to apply it?"),
			() => window.location.reload(),
		);
	},
});
