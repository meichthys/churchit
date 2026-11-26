// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Person", {
	setup(frm) {
		// No "+" in Connections: the first four link through a child table, so "+" would open a blank record,
		// and the last three come from the Check-In Station or the website, not from a form.
		frm.can_make_methods = {
			Person: () => false,
			Group: () => false,
			Function: () => false,
			Missionary: () => false,
			"Function Check-In": () => false,
			"Group Join Request": () => false,
			"Form Response": () => false,
		};

		// The grid draws a Check on every row: draw No Year on Birth rows only, like the row form.
		// The blank must be a non-empty string, because the grid formats an empty cell again against the Person.
		const year_unknown =
			frappe.meta.docfield_map["Life Event"].year_unknown;
		year_unknown.formatter = (value, df, options, doc) =>
			doc?.event_type === "Birth"
				? frappe.form.formatters.Check(value)
				: "<span></span>";

		// A date with No Year shows its month and day only, because its year is made up.
		const life_event_date = frappe.meta.docfield_map["Life Event"].date;
		life_event_date.formatter = (value, df, options, doc) =>
			value && doc?.year_unknown
				? get_month_and_day(value)
				: frappe.form.formatters.Date(value);
	},
	onload(frm) {
		// A Person changes its name by a merge only (Actions > Merge Into), which the server still allows.
		frm.meta.allow_rename = 0;
	},
	refresh(frm) {
		// The Connections tab holds the dashboard, so this alert sits above the tabs instead.
		if (frm.doc.__onload?.has_unsubscribed) {
			frm.dashboard.set_headline_alert(
				__("Unsubscribed from Church Emails"),
				"orange",
			);
		} else if (frm.doc.__onload?.bounced_email) {
			const address = frappe.utils.escape_html(
				frm.doc.__onload.bounced_email,
			);
			frm.dashboard.set_headline_alert(
				__(
					"Email bounced: {0}. Church Emails skip it until you correct it or untick Bounced.",
					[address],
				),
				"orange",
			);
		}

		// Whether AI is in use, under Keep Out of Churchit's AI Features (churchit.ai.opt_outs).
		const ai_state = frm.doc.__onload?.ai_state;
		frm.get_field("ai_status").$wrapper.html(
			ai_state
				? `<p class="text-muted small">${frappe.utils.escape_html(ai_state)}</p>`
				: "",
		);

		show_login_church(frm);
		frm.saved_user = frm.doc.user;
		show_without_year(
			frm.fields_dict.anniversary,
			() => frm.doc.anniversary_year_unknown,
		);
		if (!frm.is_new()) {
			add_actions(frm);
			show_background_check_status(frm);
			show_alert_notes(frm);
			add_merge_menu_item(frm);
			add_remove_personal_data_menu_item(frm);
		}
	},
	anniversary_year_unknown(frm) {
		frm.fields_dict.anniversary.set_formatted_input(frm.doc.anniversary);
	},
	after_save(frm) {
		// after_save runs before refresh, so saved_user is still the login before this save.
		const login = frm.doc.__onload?.login_church_note;
		if (login && frm.doc.user !== frm.saved_user)
			warn_about_login_church(frm, login);
	},
});

frappe.ui.form.on("Life Event", {
	form_render(frm, cdt, cdn) {
		show_without_year(
			get_row_date_control(frm, cdn),
			() => locals[cdt][cdn].year_unknown,
		);
	},
	year_unknown(frm, cdt, cdn) {
		get_row_date_control(frm, cdn)?.set_formatted_input(
			locals[cdt][cdn].date,
		);
	},
});

function get_row_date_control(frm, cdn) {
	return frm.fields_dict.life_events.grid.get_row(cdn).grid_form?.fields_dict
		.date;
}

// Shows the Date *control* as month and day while *is_year_unknown()*. Only the text changes: the date keeps
// its year, and the date picker still sets a whole date.
function show_without_year(control, is_year_unknown) {
	if (!control || control.shows_without_year) return;
	control.shows_without_year = true;
	const set_formatted_input = control.set_formatted_input.bind(control);
	control.set_formatted_input = (value) => {
		set_formatted_input(value);
		if (value && is_year_unknown())
			control.$input.val(get_month_and_day(value));
	};
	control.set_formatted_input(control.value);
}

function get_month_and_day(value) {
	return new Intl.DateTimeFormat(frappe.boot.lang, {
		month: "long",
		day: "numeric",
		timeZone: "UTC",
	}).format(new Date(value));
}

// Record actions under one Actions button, for a saved person.
function add_actions(frm) {
	const action = (label, fn) =>
		frm.add_custom_button(label, fn, __("Actions"));
	add_note_action(frm, action);

	if (frm.doc.last_name && !frm.doc.__onload?.is_primary_contact) {
		action(__("New Family From Person"), () =>
			frm.call("new_family_from_person").then(() => frm.reload_doc()),
		);
	}

	const has_email = (frm.doc.emails || []).some((row) => row.email_address);
	if (has_email && !frm.doc.user) {
		action(
			__("Invite to Portal"),
			() => refuse_without_email(frm) || frm.call("invite_to_portal"),
		);
	}

	add_details_link_action(frm, action);

	const login = frm.doc.__onload?.login_church_note;
	if (login?.can_limit) {
		action(
			__("Limit Login to {0}", [frappe.utils.escape_html(login.church)]),
			() => limit_login(frm),
		);
	}

	if (
		frm.doc.__onload?.has_unsubscribed &&
		frappe.model.can_write("Person")
	) {
		action(__("Resubscribe to Church Emails"), () =>
			frm
				.call("resubscribe_to_church_emails")
				.then(() => frm.reload_doc()),
		);
	}
}

// A staff login keeps the churches it works in when it is linked (Person.login_church_note),
// so say so by the field when this person's church is not one of them.
function show_login_church(frm) {
	const login = frm.doc.__onload?.login_church_note;
	if (!login) {
		frm.set_df_property(
			"user",
			"description",
			frappe.meta.get_docfield("Person", "user").description,
		);
		return;
	}
	const [works_in, church] = [login.works_in, login.church].map(
		frappe.utils.escape_html,
	);
	let description = __("This login works in {0}, not in {1}.", [
		works_in,
		church,
	]);
	if (login.can_limit) {
		description +=
			" " + __("Actions > Limit Login to {0} changes that.", [church]);
	}
	frm.set_df_property("user", "description", description);
}

// Linking a staff login does not move it to this person's church, so say so on the save that links it.
function warn_about_login_church(frm, login) {
	const [user, works_in, church] = [
		frm.doc.user,
		login.works_in,
		login.church,
	].map(frappe.utils.escape_html);
	let message = __(
		"{0} works in {1}, not in {2}. Linking it to this person does not change that.",
		[`<b>${user}</b>`, works_in, church],
	);
	if (!login.can_limit) {
		message +=
			" " +
			__(
				"Ask someone who works across every church to limit it to {0}.",
				[church],
			);
	}
	frappe.msgprint({
		title: __("Login Works in Another Church"),
		indicator: "orange",
		message,
		primary_action: login.can_limit && {
			label: __("Limit Login to {0}", [church]),
			action: () => limit_login(frm).then(() => frappe.hide_msgprint()),
		},
	});
}

function limit_login(frm) {
	return frappe
		.xcall(
			"churchit.church_foundations.church_access.limit_login_to_church",
			{
				person: frm.doc.name,
			},
		)
		.then(() => frm.reload_doc());
}

// Show the most recent background check so leaders can see at a glance whether this person is
// cleared to serve. The dashboard sits on the Connections tab, so a check that does not clear
// the person goes above the tabs instead.
function show_background_check_status(frm) {
	if (!frappe.model.can_read("Background Check")) return;
	const person = frm.doc.name;
	frappe.db
		.get_list("Background Check", {
			filters: { person },
			fields: ["check_type", "status", "expires_on"],
			order_by: "requested_on desc, creation desc",
			limit: 1,
		})
		.then((rows) => {
			if (!rows || !rows.length || frm.doc.name !== person) return;
			const check = rows[0];
			let label = `${__("Background Check")}: ${__(check.status)} (${check.check_type})`;
			if (check.status !== "Cleared") {
				const color = check.status === "Not Cleared" ? "red" : "orange";
				frm.dashboard.set_headline_alert(
					frappe.utils.escape_html(label),
					color,
				);
				return;
			}
			if (check.expires_on) {
				label += ` ${__("until")} ${frappe.datetime.str_to_user(check.expires_on)}`;
			}
			frm.dashboard.add_indicator(label, "green");
		});
}

// The alert notes this user may read, at the top of the form. The server leaves out the others.
function show_alert_notes(frm) {
	if (!frappe.model.can_read("Person Note")) return;
	const person = frm.doc.name;
	const method = "churchit.church_people.notes.get_alert_notes";
	frappe.xcall(method, { person }, "GET").then((notes) => {
		if (!notes.length || frm.doc.name !== person) return;
		const lines = notes.map((note) => {
			const category = frappe.utils.escape_html(__(note.category));
			const link = frappe.utils.get_form_link(
				"Person Note",
				note.name,
				true,
				category,
			);
			const text = frappe.utils.escape_html(
				frappe.utils.html2text(note.note),
			);
			return `<div>${link}: ${text}</div>`;
		});
		frm.set_intro(lines.join(""), "red");
	});
}

// Say why an email cannot go out, in words for this user's role. True when it said so.
function refuse_without_email(frm) {
	const problem = frm.doc.__onload?.email_problem;
	if (problem) {
		frappe.msgprint({
			title: __("Email Not Configured"),
			message: problem,
			indicator: "orange",
		});
	}
	return !!problem;
}

// The link lets the person change their own details without a login, once, for 7 days.
function add_details_link_action(frm, action) {
	const has_email = (frm.doc.emails || []).some(
		(row) => row.is_primary && row.email_address,
	);
	if (!frm.perm[0]?.write || !has_email) return;
	action(
		__("Send Details Link"),
		() =>
			refuse_without_email(frm) ||
			frappe
				.xcall(
					"churchit.church_people.details_link.send_details_link",
					{
						person: frm.doc.name,
					},
				)
				.then((email) =>
					frappe.show_alert({
						message: __("Details link sent to {0}", [
							frappe.utils.escape_html(email),
						]),
						indicator: "green",
					}),
				),
	);
}

// A dialog keeps the person's unsaved changes; the Activity list and the alerts then load the new note.
function add_note_action(frm, action) {
	if (!frappe.model.can_create("Person Note")) return;
	action(__("Add Person Note"), () => {
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
			true,
		);
	});
}

// Once a new person has a first name and an email or phone, note the people they may already be, without
// blocking the save. The contact tables are shared with Family, so their handlers check the form.
const check_for_possible_matches = frappe.utils.debounce((frm) => {
	if (frm.doctype !== "Person" || !frm.is_new()) return;
	const own_values = (rows, field) =>
		(rows || [])
			.filter((row) => row[field] && !row.shared_from)
			.map((row) => row[field]);
	const birth = (frm.doc.life_events || []).find(
		(row) => row.event_type === "Birth" && row.date && !row.year_unknown,
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
	if (
		!candidate.first_name ||
		!(candidate.emails.length || candidate.phones.length)
	) {
		frm.set_intro("");
		return;
	}
	frappe
		.xcall(
			"churchit.church_people.matching.get_possible_matches",
			{ candidate },
			"GET",
		)
		.then((matches) => {
			if (frm.is_new())
				frm.set_intro(possible_matches_note(matches), "yellow");
		});
}, 500);

function possible_matches_note(matches) {
	if (!matches.length) return "";
	const people = matches.map((match) => {
		const link = frappe.utils.get_form_link(
			"Person",
			match.person,
			true,
			frappe.utils.escape_html(match.full_name),
		);
		const reasons = match.reasons.map((reason) =>
			frappe.utils.escape_html(__(reason)),
		);
		return `${link} (${reasons.join(", ")})`;
	});
	return __("This person may already be in the directory: {0}", [
		people.join("; "),
	]);
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

// Set on the form, not as a field default: the server would fill a cleared date back in.
frappe.ui.form.on("Position", {
	positions_add(frm, cdt, cdn) {
		frappe.model.set_value(
			cdt,
			cdn,
			"start_date",
			frappe.datetime.get_today(),
		);
	},
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
					get_query: () => ({
						filters: { name: ["!=", frm.doc.name] },
					}),
					description: __(
						"Everything that names {0} moves to this person, and {0} is deleted. This person keeps their own details, except the ones you choose below, and gets the ones they do not have from {0}. You cannot undo a merge.",
						[name],
					),
					onchange: () =>
						churchit.merge_choices.render(
							choices(),
							dialog.get_value("keep"),
							frm.doc.name,
						),
				},
				{ fieldname: "choices", fieldtype: "HTML" },
			],
			primary_action_label: __("Merge"),
			primary_action({ keep }) {
				const take_from_removed =
					churchit.merge_choices.get_taken(choices());
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
				"Remove the personal data of {0}? The record stays, so their giving and attendance still count. Their first name, contact details, notes, photo, birth date, family, spouse and portal login go, and the last name stays. You cannot undo this.",
				[frappe.utils.escape_html(frm.doc.full_name)],
			),
			() =>
				frappe
					.call({
						method: "churchit.church_people.privacy.anonymize_person",
						args: { person: frm.doc.name },
						freeze: true,
					})
					.then(() => frm.reload_doc()),
		);
	});
}
