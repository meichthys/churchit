// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

// Interactive behaviour for the shared contact tables (Email Address, Phone
// Number, Postal Address). These child doctypes are used by Person, Family and
// Missionary, so the handlers are registered on the child doctypes themselves
// and apply on whichever parent form they appear in.
//
// The server re-applies the same rules in churchit.contacts.validate_contact_tables;
// this file exists so the checkboxes behave like radio buttons while editing
// rather than only being corrected on save.

(() => {
	// Ticking a flag on one row clears it on every sibling row, so the check
	// reads as "this one" instead of silently being overruled on save.
	function clear_flag_on_siblings(frm, cdt, cdn, flag) {
		const row = locals[cdt][cdn];
		if (!row || !row[flag]) return;

		for (const sibling of frm.doc[row.parentfield] || []) {
			if (sibling.name !== cdn && sibling[flag]) {
				frappe.model.set_value(sibling.doctype, sibling.name, flag, 0);
			}
		}
	}

	// Filling in the first row of an empty table marks it primary, so a record
	// with a single email/phone/address never sits there with nothing chosen.
	function claim_primary_if_unset(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row) return;

		const rows = frm.doc[row.parentfield] || [];
		if (!rows.some((sibling) => sibling.is_primary)) {
			frappe.model.set_value(cdt, cdn, "is_primary", 1);
		}
	}

	frappe.ui.form.on("Email Address", {
		is_primary(frm, cdt, cdn) {
			clear_flag_on_siblings(frm, cdt, cdn, "is_primary");
		},
		email_address(frm, cdt, cdn) {
			claim_primary_if_unset(frm, cdt, cdn);
		},
	});

	frappe.ui.form.on("Phone Number", {
		is_primary(frm, cdt, cdn) {
			clear_flag_on_siblings(frm, cdt, cdn, "is_primary");
		},
		phone_number(frm, cdt, cdn) {
			claim_primary_if_unset(frm, cdt, cdn);
		},
	});

	frappe.ui.form.on("Postal Address", {
		is_primary(frm, cdt, cdn) {
			clear_flag_on_siblings(frm, cdt, cdn, "is_primary");
		},
		is_mailing_address(frm, cdt, cdn) {
			clear_flag_on_siblings(frm, cdt, cdn, "is_mailing_address");
		},
		address(frm, cdt, cdn) {
			claim_primary_if_unset(frm, cdt, cdn);
		},
	});
})();
