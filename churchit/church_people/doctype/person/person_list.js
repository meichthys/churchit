// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

const LIST_ACTIONS = "churchit.church_people.list_actions";
const ADD_TO_GROUP = "churchit.church_people.doctype.group.group.add_people";

// The report view runs these settings too, so a saved smart list offers the same actions.
frappe.listview_settings["Person"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Rolodex"), () => {
			frappe.route_options = { view: "people" };
			frappe.set_route("rolodex");
		});
		const add_action = (label, action) =>
			listview.page.add_action_item(label, () => {
				const people = listview.get_checked_items(true);
				if (!people.length) return frappe.msgprint(__("Select at least one person."));
				action(people);
			});

		if (frappe.model.can_create("Church Email"))
			add_action(__("New Church Email"), new_church_email);
		add_action(__("Email"), (people) => email_in_bcc("get_people_emails", { people }));
		add_action(__("Email Household Adults"), (people) =>
			email_in_bcc("get_household_adult_emails", { people })
		);
		add_action(__("Open in Rolodex"), (people) => {
			frappe.route_options = { view: "people", people };
			frappe.set_route("rolodex");
		});
		if (frappe.model.can_write("Group")) add_action(__("Add to Group"), add_to_group);
		if (frappe.model.can_write("Person"))
			add_action(__("Mark Inactive"), (people) => mark_inactive(listview, people));
		add_action(__("Check In"), (people) => check_in(listview, people));
		add_action(__("Print Name Tags"), (persons) => church.name_tags.print_for({ persons }));
	},
};

// The people go in BCC, so no one sees the others' addresses.
function email_in_bcc(method, args) {
	frappe.xcall(`${LIST_ACTIONS}.${method}`, args).then((result) => {
		const names = (list) => (list || []).map(frappe.utils.escape_html).join(", ");
		const notes = [
			result.without_email.length &&
				__("No email address for {0}.", [names(result.without_email)]),
			result.refused?.length &&
				__("Left out because they do not allow email: {0}.", [names(result.refused)]),
			result.without_adults?.length &&
				__("No Adult on file in the household of {0}.", [names(result.without_adults)]),
		].filter(Boolean);
		if (!result.emails.length) {
			frappe.msgprint(notes.join("<br>") || __("No one picked has an email address."));
			return;
		}
		if (notes.length) frappe.show_alert({ message: notes.join(" "), indicator: "orange" }, 10);
		const composer = new frappe.views.CommunicationComposer({
			recipients: frappe.session.user_email,
			bcc: result.emails.join(", "),
		});
		// The composer shows a filled BCC row only once it has loaded, and loading stops early
		// for a user who cannot read Email Account.
		composer.$composer?.find('.email-composer-toggle[data-target="bcc"]').trigger("click");
	});
}

// A draft to the people picked, opened for its subject and message.
function new_church_email(people) {
	frappe
		.xcall(`${LIST_ACTIONS}.new_church_email`, { people })
		.then((name) => frappe.set_route("Form", "Church Email", name));
}

function add_to_group(people) {
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
			frappe.xcall(ADD_TO_GROUP, { group, group_role, people }).then((result) => {
				dialog.hide();
				const title = frappe.utils.get_link_title("Group", group) || group;
				let message = __("Added {0} to {1}.", [
					result.added,
					frappe.utils.escape_html(title),
				]);
				if (result.already_members === 1) message += " " + __("1 was already a member.");
				if (result.already_members > 1)
					message += " " + __("{0} were already members.", [result.already_members]);
				frappe.show_alert({ message, indicator: "green" });
			});
		},
	});
	frappe.db
		.get_value("Group Role", { role: "Member" }, "name")
		.then((r) => dialog.set_value("group_role", r.message?.name));
	dialog.show();
}

function mark_inactive(listview, people) {
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
					"Status becomes Inactive and Inactive Since today. Anyone already Inactive keeps their reason."
				),
			},
		],
		primary_action_label: __("Mark Inactive"),
		primary_action: ({ reason }) => {
			frappe.xcall(`${LIST_ACTIONS}.mark_inactive`, { people, reason }).then((result) => {
				dialog.hide();
				listview.refresh();
				let message = __("Marked {0} inactive.", [count_people(result.marked)]);
				if (result.already_inactive)
					message += " " + __("{0} already inactive.", [result.already_inactive]);
				frappe.show_alert({ message, indicator: "green" });
			});
		},
	});
	dialog.show();
}

function check_in(listview, people) {
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
		primary_action(values) {
			frappe.call({
				method: "churchit.church_ministries.doctype.function_check_in.function_check_in.check_in_persons",
				args: {
					function_name: values.function,
					persons: people,
				},
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({
							message: __("{0} person(s) checked in.", [people.length]),
							indicator: "green",
						});
						dialog.hide();
						listview.refresh();
					}
				},
			});
		},
	});
	dialog.show();
}

function count_people(count) {
	return count === 1 ? __("1 person") : __("{0} people", [count]);
}
