// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

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

	// Shared From links to a record of the same doctype as the form, which the
	// link search reads from the hidden type field before the server sets it.
	function set_shared_from_type(frm, cdt, cdn) {
		locals[cdt][cdn].shared_from_type = frm.doctype;
	}

	// Shared From offers only the other records that already hold the row's value.
	const SHARED_TABLES = [
		[
			"emails",
			"email_address",
			__("Only records that already have this email address are listed."),
		],
		[
			"phones",
			"phone_number",
			__("Only records that already have this phone number are listed."),
		],
	];

	function set_shared_from_queries(frm) {
		for (const [fieldname, value_field] of SHARED_TABLES) {
			frm.set_query("shared_from", fieldname, (doc, cdt, cdn) => ({
				query: "churchit.contacts.search_holders",
				filters: {
					child_doctype: cdt,
					value: locals[cdt][cdn][value_field],
					parent: doc.name,
				},
			}));
		}
	}

	// Replaces Frappe's "Filtered by" line, which would list the query's arguments.
	function describe_shared_from_filter(frm) {
		for (const [fieldname, , description] of SHARED_TABLES) {
			frm.fields_dict[fieldname].grid.update_docfield_property(
				"shared_from",
				"filter_description",
				description
			);
		}
	}

	for (const parent of ["Person", "Family", "Missionary", "Missionary Agency"]) {
		frappe.ui.form.on(parent, {
			setup: set_shared_from_queries,
			refresh: describe_shared_from_filter,
		});
	}

	frappe.ui.form.on("Email Address", {
		emails_add: set_shared_from_type,
		is_primary(frm, cdt, cdn) {
			clear_flag_on_siblings(frm, cdt, cdn, "is_primary");
		},
		email_address(frm, cdt, cdn) {
			claim_primary_if_unset(frm, cdt, cdn);
		},
	});

	frappe.ui.form.on("Phone Number", {
		phones_add: set_shared_from_type,
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
