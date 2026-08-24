// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

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
