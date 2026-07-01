// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Group", {
	refresh(frm) {
		const grid = frm.fields_dict.members.grid;
		grid.add_custom_button(__("Email Group"), () => email_members(frm, false));
		grid.add_custom_button(__("Email Selected"), () => email_members(frm, true));

		// Create a reusable Frappe Email Group (newsletter list) from the members
		if (!frm.is_new()) {
			frm.add_custom_button(__("Create Email Group"), () => create_email_group(frm), __("Actions"));
		}
	},
});

function create_email_group(frm) {
	if (!(frm.doc.members || []).length) {
		frappe.msgprint(__("No members in this group."));
		return;
	}
	frappe.call({
		method: "churchit.church_people.doctype.group.group.create_email_group",
		args: { group: frm.doc.name },
		freeze: true,
		freeze_message: __("Creating email group…"),
		callback(r) {
			if (!r.message) return;
			const m = r.message;
			const link = `/app/email-group/${encodeURIComponent(m.email_group)}`;
			let msg = __("Email group {0} now has {1} subscriber(s).", [
				`<a href="${link}"><b>${frappe.utils.escape_html(m.email_group)}</b></a>`,
				m.total_members,
			]);
			if (m.missing && m.missing.length) {
				msg += "<br><br>" + __("⚠️ Skipped {0} member(s) with no email address:", [m.missing.length])
					+ "<ul>" + m.missing.map((n) => `<li>${frappe.utils.escape_html(n)}</li>`).join("") + "</ul>";
			}
			frappe.msgprint({ title: __("Email Group Ready"), indicator: "green", message: msg });
		},
	});
}

function email_members(frm, selected_only) {
	const grid = frm.fields_dict.members.grid;
	const rows = selected_only ? grid.get_selected_children() : frm.doc.members || [];
	const persons = rows.map((r) => r.person).filter(Boolean);

	if (!persons.length) {
		frappe.msgprint(selected_only ? __("Please select at least one member.") : __("No members in this group."));
		return;
	}

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Person",
			filters: { name: ["in", persons] },
			fields: ["name", "email"],
			limit_page_length: 0,
		},
		callback(r) {
			const results = r.message || [];
			const emails = results.filter((p) => p.email).map((p) => p.email);
			const missing = results.filter((p) => !p.email).map((p) => p.name);

			if (missing.length) {
				frappe.msgprint({
					title: __("Missing Email Addresses"),
					indicator: "orange",
					message: __("⚠️ The following members have no email address and will not be included:")
						+ "<ul>" + missing.map((n) => `<li>${n}</li>`).join("") + "</ul>",
				});
			}

			window.location.href = "mailto:" + emails.join(",");
		},
	});
}
