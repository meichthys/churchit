// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The actions on a set of people: the Person list runs them on the people ticked, the Rolodex on
// its saved cards. Each page names the actions it offers, in its own order.
frappe.provide("churchit.people_actions");

(function () {
	const LIST_ACTIONS = "churchit.church_people.list_actions";
	const ADD_TO_GROUP =
		"churchit.church_people.doctype.group.group.add_people";
	const CHECK_IN =
		"churchit.church_ministries.doctype.function_check_in.function_check_in.check_in_persons";

	// The actions named by *keys* that the user may run, in that order, each as { key, label, run }.
	// run(people, done) calls done after it changes people, so the page can show the change.
	// open_email(emails, notes) shows the addresses an email action found.
	churchit.people_actions.get = function (
		keys,
		{ open_email = open_composer } = {},
	) {
		const can_write_people = frappe.model.can_write("Person");
		const actions = {
			edit: {
				label: __("Edit"),
				is_allowed: can_write_people,
				run: edit,
			},
			check_in: {
				label: __("Check In"),
				is_allowed: frappe.model.can_create("Function Check-In"),
				run: check_in,
			},
			add_to_group: {
				label: __("Add to Group"),
				is_allowed: frappe.model.can_write("Group"),
				run: add_to_group,
			},
			add_tags: {
				label: __("Add Tags"),
				is_allowed: can_write_people,
				run: (people, done) => bulk_operations().add_tags(people, done),
			},
			assign_to: {
				label: __("Assign To"),
				run: (people, done) => bulk_operations().assign(people, done),
			},
			new_church_email: {
				label: __("New Church Email"),
				is_allowed: frappe.model.can_create("Church Email"),
				run: new_church_email,
			},
			email: {
				label: __("Email"),
				run: (people) => email(people, open_email),
			},
			email_household_adults: {
				label: __("Email Household Adults"),
				run: (people) =>
					email_in_bcc(
						"get_household_adult_emails",
						{ people },
						open_email,
					),
			},
			mark_inactive: {
				label: __("Mark Inactive"),
				is_allowed: can_write_people,
				run: mark_inactive,
			},
			verify_contact_info: {
				label: __("Verify Contact Info"),
				is_allowed: frappe.model.can_create("Contact Verification"),
				run: new_contact_verification,
			},
			print_name_tags: {
				label: __("Print Name Tags"),
				run: (persons) => church.name_tags.print_for({ persons }),
			},
			open_in_rolodex: {
				label: __("Open in Rolodex"),
				run: open_in_rolodex,
			},
			open_in_people_list: {
				label: __("Open in People List"),
				run: (people) =>
					frappe.set_route("List", "Person", {
						name: ["in", people],
					}),
			},
		};
		// A page script can name a key that a 12-hour-old copy of this script does not have yet.
		return keys
			.filter((key) => actions[key] && actions[key].is_allowed !== false)
			.map((key) => ({ key, ...actions[key] }));
	};

	// The emails of *people* who allow email, for open_email to show.
	function email(people, open_email = open_composer) {
		email_in_bcc("get_people_emails", { people }, open_email);
	}
	churchit.people_actions.email = email;

	// The addresses go in BCC, so no one sees the others.
	function email_in_bcc(method, args, open_email = open_composer) {
		// A long list waits on a permission check per person, so hold the screen until it answers.
		frappe
			.xcall(`${LIST_ACTIONS}.${method}`, args, "POST", { freeze: true })
			.then((result) => {
				const names = (list) =>
					(list || []).map(frappe.utils.escape_html).join(", ");
				const notes = [
					result.without_email.length &&
						__("No email address for {0}.", [
							names(result.without_email),
						]),
					result.refused?.length &&
						__("Left out because they do not allow email: {0}.", [
							names(result.refused),
						]),
					result.without_adults?.length &&
						__("No Adult on file in the household of {0}.", [
							names(result.without_adults),
						]),
				].filter(Boolean);
				if (!result.emails.length) {
					frappe.msgprint(
						notes.join("<br>") ||
							__("No one picked has an email address."),
					);
					return;
				}
				open_email(result.emails, notes);
			});
	}
	churchit.people_actions.email_in_bcc = email_in_bcc;

	function open_composer(emails, notes) {
		if (notes.length)
			frappe.show_alert(
				{ message: notes.join(" "), indicator: "orange" },
				10,
			);
		const composer = new frappe.views.CommunicationComposer({
			recipients: frappe.session.user_email,
			bcc: emails.join(", "),
		});
		// The composer shows a filled BCC row only once it has loaded, and loading stops early
		// for a user who cannot read Email Account.
		composer.$composer
			?.find('.email-composer-toggle[data-target="bcc"]')
			.trigger("click");
	}

	function bulk_operations() {
		return new frappe.ui.BulkOperations({ doctype: "Person" });
	}

	// Frappe's bulk edit, with the fields its Kanban board offers that the user may change.
	// Child table fields are left out: a value there would overwrite every row.
	function edit(people, done) {
		frappe.model.with_doctype("Person", () => {
			const fields = {};
			for (const df of frappe.meta.get_docfields("Person")) {
				const is_editable =
					df.fieldname &&
					frappe.model.is_value_type(df) &&
					df.fieldtype !== "Read Only" &&
					!df.hidden &&
					!df.read_only &&
					!df.is_virtual &&
					frappe.perm.has_perm("Person", df.permlevel, "write");
				if (is_editable)
					fields[df.fieldname] = {
						...df,
						is_child_field: false,
						translated_label: __(df.label, null, "Person"),
					};
			}
			bulk_operations().edit(people, fields, done);
		});
	}

	function check_in(people, done) {
		const dialog = new frappe.ui.Dialog({
			title: __("Check In"),
			fields: [
				{
					fieldtype: "Link",
					fieldname: "function",
					label: __("Function"),
					options: "Function",
					reqd: 1,
				},
			],
			primary_action_label: __("Check In"),
			primary_action: (values) => {
				frappe
					.xcall(CHECK_IN, {
						function_name: values.function,
						persons: people,
					})
					.then(() => {
						dialog.hide();
						frappe.show_alert({
							message: __("{0} person(s) checked in.", [
								people.length,
							]),
							indicator: "green",
						});
						done();
					});
			},
		});
		dialog.show();
	}

	function add_to_group(people, done) {
		const dialog = new frappe.ui.Dialog({
			title: __("Add {0} to a group", [count_people(people.length)]),
			fields: [
				{
					fieldtype: "Link",
					fieldname: "group",
					label: __("Group"),
					options: "Group",
					reqd: 1,
				},
				{
					fieldtype: "Link",
					fieldname: "group_role",
					label: __("Role"),
					options: "Group Role",
				},
			],
			primary_action_label: __("Add"),
			primary_action: ({ group, group_role }) => {
				frappe
					.xcall(ADD_TO_GROUP, { group, group_role, people })
					.then((result) => {
						dialog.hide();
						const title =
							frappe.utils.get_link_title("Group", group) ||
							group;
						let message = __("Added {0} to {1}.", [
							result.added,
							frappe.utils.escape_html(title),
						]);
						if (result.already_members === 1)
							message += " " + __("1 was already a member.");
						if (result.already_members > 1)
							message +=
								" " +
								__("{0} were already members.", [
									result.already_members,
								]);
						frappe.show_alert({ message, indicator: "green" });
						done();
					});
			},
		});
		frappe.db
			.get_value("Group Role", { role: "Member" }, "name")
			.then((r) => dialog.set_value("group_role", r.message?.name));
		dialog.show();
	}

	// A draft to the people picked, opened for its subject and message.
	function new_church_email(people) {
		frappe
			.xcall(`${LIST_ACTIONS}.new_church_email`, { people })
			.then((name) => frappe.set_route("Form", "Church Email", name));
	}

	function mark_inactive(people, done) {
		const dialog = new frappe.ui.Dialog({
			title: __("Mark {0} Inactive", [count_people(people.length)]),
			fields: [
				{
					fieldtype: "Link",
					fieldname: "reason",
					label: __("Inactive Reason"),
					options: "Inactive Reason",
					reqd: 1,
					description: __(
						"Status becomes Inactive and Inactive Since today. Anyone already Inactive keeps their reason.",
					),
				},
			],
			primary_action_label: __("Mark Inactive"),
			primary_action: ({ reason }) => {
				frappe
					.xcall(`${LIST_ACTIONS}.mark_inactive`, { people, reason })
					.then((result) => {
						dialog.hide();
						let message = __("Marked {0} inactive.", [
							count_people(result.marked),
						]);
						if (result.already_inactive)
							message +=
								" " +
								__("{0} already inactive.", [
									result.already_inactive,
								]);
						frappe.show_alert({ message, indicator: "green" });
						done();
					});
			},
		});
		dialog.show();
	}

	// A new Contact Verification with a card for each person picked, opened unsaved for its title.
	function new_contact_verification(people) {
		frappe.model.with_doctype("Contact Verification", () => {
			const doc = frappe.model.get_new_doc("Contact Verification");
			for (const person of people)
				frappe.model.add_child(doc, "people").person = person;
			frappe.set_route("Form", "Contact Verification", doc.name);
		});
	}

	function open_in_rolodex(people) {
		frappe.route_options = { view: "people", people };
		frappe.set_route("rolodex");
	}

	function count_people(count) {
		return count === 1 ? __("1 person") : __("{0} people", [count]);
	}
})();
