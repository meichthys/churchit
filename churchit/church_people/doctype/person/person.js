// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Person", {
	refresh(frm) {
		// Calculate marriage years from anniversary
		if (frm.doc.anniversary) {
			const today = frappe.datetime.get_today();
			const anniversary = frm.doc.anniversary;
			const anniversaryDate = new Date(anniversary);
			const todayDate = new Date(today);

			let years = todayDate.getFullYear() - anniversaryDate.getFullYear();

			if (
				todayDate.getMonth() < anniversaryDate.getMonth() ||
				(todayDate.getMonth() === anniversaryDate.getMonth() &&
					todayDate.getDate() < anniversaryDate.getDate())
			) {
				years--;
			}

			frm.doc.marriage_years = years;
			frm.refresh_field("marriage_years");
		}

		// Add 'New Family From Person' button if Last Name is populated and person is not already a family's primary contact
		if (frm.doc.last_name && !frm.doc.__onload?.is_primary_contact) {
			frm.add_custom_button(__("New Family From Person"), function () {
				frm.call("new_family_from_person").then(() => frm.reload_doc());
			});
		}

		// Add 'Invite to Portal' button if an email is on file and no Portal User is linked
		const has_email = (frm.doc.emails || []).some((row) => row.email_address);
		if (has_email && !frm.doc.user) {
			frm.add_custom_button(__("Invite to Portal"), function () {
				frm.call("invite_to_portal");
			});
		}

		if (!frm.is_new()) {
			show_background_check_status(frm);
			show_alert_notes(frm);
		}

		if (frm.doc.__onload?.has_unsubscribed) {
			frm.dashboard.add_indicator(__("Unsubscribed from Church Emails"), "orange");
			if (frappe.model.can_write("Person")) {
				frm.add_custom_button(__("Resubscribe to Church Emails"), () =>
					frm.call("resubscribe_to_church_emails").then(() => frm.reload_doc())
				);
			}
		}

		if (!frm.is_new()) {
			add_note_menu_item(frm);
			add_details_link_menu_item(frm);
			add_merge_menu_item(frm);
			show_engagement(frm);
			add_remove_personal_data_menu_item(frm);
		}

		// Add 'Person Tour' button
		frm.add_custom_button(__("Tutorial"), function () {
			frm.tour.init("Person").then(() => frm.tour.start());
		});
	},
});

// Show the most recent background check on the form dashboard so leaders can
// see at a glance whether this person is cleared to serve.
function show_background_check_status(frm) {
	if (!frappe.model.can_read("Background Check")) return;
	frappe.db
		.get_list("Background Check", {
			filters: { person: frm.doc.name },
			fields: ["check_type", "status", "expires_on"],
			order_by: "requested_on desc, creation desc",
			limit: 1,
		})
		.then((rows) => {
			if (!rows || !rows.length) return;
			const check = rows[0];
			const colors = { Cleared: "green", "Not Cleared": "red", Expired: "gray" };
			let label = `${__("Background Check")}: ${__(check.status)} (${check.check_type})`;
			if (check.status === "Cleared" && check.expires_on) {
				label += ` ${__("until")} ${frappe.datetime.str_to_user(check.expires_on)}`;
			}
			frm.dashboard.add_indicator(label, colors[check.status] || "orange");
		});
}

// The alert notes this user may read, at the top of the form. The server leaves out the others.
function show_alert_notes(frm) {
	if (!frappe.model.can_read("Person Note")) return;
	const person = frm.doc.name;
	frappe.xcall("churchit.church_people.notes.get_alert_notes", { person }).then((notes) => {
		if (!notes.length || frm.doc.name !== person) return;
		const lines = notes.map((note) => {
			const category = frappe.utils.escape_html(__(note.category));
			const link = frappe.utils.get_form_link("Person Note", note.name, true, category);
			const text = frappe.utils.escape_html(frappe.utils.html2text(note.note));
			return `<div>${link}: ${text}</div>`;
		});
		frm.set_intro(lines.join(""), "red");
	});
}

// The link lets the person change their own details without a login, once, for 7 days.
function add_details_link_menu_item(frm) {
	const has_email = (frm.doc.emails || []).some((row) => row.is_primary && row.email_address);
	if (!frm.perm[0]?.write || !has_email) return;
	frm.page.add_menu_item(__("Send Details Link"), () =>
		frappe
			.xcall("churchit.church_people.details_link.send_details_link", {
				person: frm.doc.name,
			})
			.then((email) =>
				frappe.show_alert({
					message: __("Details link sent to {0}", [frappe.utils.escape_html(email)]),
					indicator: "green",
				})
			)
	);
}

// The stored attendance, groups, serving and giving figures, as indicators on the form dashboard.
// Giving shows only to a reader who may read its permission level.
function show_engagement(frm) {
	const doc = frm.doc;
	const add = (label, value, color) =>
		frm.dashboard.add_indicator(`${label}: ${frappe.utils.escape_html(String(value))}`, color);
	const date = (value) => frappe.datetime.str_to_user(value);

	if (doc.first_attended_on) {
		add(__("First Attended"), date(doc.first_attended_on), "blue");
		add(__("Last Attended"), date(doc.last_attended_on), "blue");
	}
	add(
		__("Times Attended (90 Days)"),
		doc.times_attended_90d || 0,
		doc.times_attended_90d ? "green" : "orange"
	);
	add(__("Groups"), doc.group_count || 0, doc.group_count ? "green" : "orange");
	if (doc.last_served_on) {
		add(__("Last Served"), date(doc.last_served_on), "blue");
	}
	if (frm.perm[2]?.read && doc.last_gift_on) {
		add(__("Last Gift"), date(doc.last_gift_on), doc.is_lapsed_giver ? "orange" : "green");
	}
}

// A dialog keeps the person's unsaved changes; the Activity list and the alerts then load the new note.
function add_note_menu_item(frm) {
	if (!frappe.model.can_create("Person Note")) return;
	frm.page.add_menu_item(__("Add Person Note"), () => {
		const note = frappe.model.get_new_doc("Person Note");
		note.person = frm.doc.name;
		const after_insert = () => {
			frappe
				.xcall("frappe.desk.form.load.get_docinfo", {
					doctype: frm.doctype,
					name: frm.docname,
				})
				.then(() => frm.timeline.refresh());
			show_alert_notes(frm);
		};
		const set_category_query = (dialog) => {
			dialog.fields_dict.category.get_query = () => ({
				query: "churchit.church_people.notes.search_categories_to_add",
			});
		};
		frappe.ui.form.make_quick_entry(
			"Person Note",
			after_insert,
			set_category_query,
			note,
			true
		);
	});
}

// Once a new person has a first name and an email or phone, note the people they may already be, without
// blocking the save. The contact tables are shared with Family, so their handlers check the form.
const check_for_possible_matches = frappe.utils.debounce((frm) => {
	if (frm.doctype !== "Person" || !frm.is_new()) return;
	const own_values = (rows, field) =>
		(rows || []).filter((row) => row[field] && !row.shared_from).map((row) => row[field]);
	const birth = (frm.doc.life_events || []).find(
		(row) => row.event_type === "Birth" && row.date && !row.year_unknown
	);
	const candidate = {
		first_name: frm.doc.first_name,
		last_name: frm.doc.last_name,
		nickname: frm.doc.nickname,
		middle_name: frm.doc.middle_name,
		previous_last_name: frm.doc.previous_last_name,
		suffix: frm.doc.suffix,
		gender: frm.doc.gender,
		birth_date: birth?.date,
		emails: own_values(frm.doc.emails, "email_address"),
		phones: own_values(frm.doc.phones, "phone_number"),
	};
	if (!candidate.first_name || !(candidate.emails.length || candidate.phones.length)) {
		frm.set_intro("");
		return;
	}
	frappe
		.xcall("churchit.church_people.matching.get_possible_matches", { candidate })
		.then((matches) => {
			if (frm.is_new()) frm.set_intro(possible_matches_note(matches), "yellow");
		});
}, 500);

function possible_matches_note(matches) {
	if (!matches.length) return "";
	const people = matches.map((match) => {
		const link = frappe.utils.get_form_link(
			"Person",
			match.person,
			true,
			frappe.utils.escape_html(match.full_name)
		);
		const reasons = match.reasons.map((reason) => frappe.utils.escape_html(__(reason)));
		return `${link} (${reasons.join(", ")})`;
	});
	return __("This person may already be in the directory: {0}", [people.join("; ")]);
}

frappe.ui.form.on("Person", {
	first_name: check_for_possible_matches,
	last_name: check_for_possible_matches,
	nickname: check_for_possible_matches,
});
frappe.ui.form.on("Email Address", {
	email_address: check_for_possible_matches,
	emails_remove: check_for_possible_matches,
});
frappe.ui.form.on("Phone Number", {
	phone_number: check_for_possible_matches,
	phones_remove: check_for_possible_matches,
});

// A merge deletes this person, so it needs the right to delete.
function add_merge_menu_item(frm) {
	if (!frappe.model.can_delete("Person")) return;
	const name = frappe.utils.escape_html(frm.doc.full_name);
	frm.page.add_menu_item(__("Merge Into…"), () => {
		const dialog = new frappe.ui.Dialog({
			title: __("Merge {0} Into Another Person", [name]),
			fields: [
				{
					fieldname: "keep",
					fieldtype: "Link",
					options: "Person",
					label: __("Person to Keep"),
					reqd: 1,
					get_query: () => ({ filters: { name: ["!=", frm.doc.name] } }),
					description: __(
						"Everything that names {0} moves to this person, and {0} is deleted. This person keeps their own details, except the ones you choose below, and gets the ones they do not have from {0}. You cannot undo a merge.",
						[name]
					),
					onchange: () =>
						churchit.merge_choices.render(
							choices(),
							dialog.get_value("keep"),
							frm.doc.name
						),
				},
				{ fieldname: "choices", fieldtype: "HTML" },
			],
			primary_action_label: __("Merge"),
			primary_action({ keep }) {
				const take_from_removed = churchit.merge_choices.get_taken(choices());
				dialog.hide();
				frappe
					.call({
						method: "churchit.church_people.merge.merge_people",
						args: { keep, remove: frm.doc.name, take_from_removed },
						freeze: true,
						freeze_message: __("Merging…"),
					})
					.then(() => frappe.set_route("Form", "Person", keep));
			},
		});
		const choices = () => dialog.get_field("choices").$wrapper;
		dialog.show();
	});
}

function add_remove_personal_data_menu_item(frm) {
	if (!frappe.user.has_role(["Church Manager", "System Manager"])) return;
	frm.page.add_menu_item(__("Remove Personal Data"), () => {
		frappe.confirm(
			__(
				"Remove the personal data of {0}? The record stays, so their giving and attendance still count. Their name, contact details, notes, photo, birth date, family, spouse and portal login go. You cannot undo this.",
				[frappe.utils.escape_html(frm.doc.full_name)]
			),
			() =>
				frappe
					.call({
						method: "churchit.church_people.privacy.anonymize_person",
						args: { person: frm.doc.name },
						freeze: true,
					})
					.then(() => frm.reload_doc())
		);
	});
}
