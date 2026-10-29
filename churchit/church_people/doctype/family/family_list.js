// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Family"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Rolodex"), () => {
			frappe.route_options = { view: "households" };
			frappe.set_route("rolodex");
		});
		listview.page.add_action_item(__("Email"), () => {
			const families = listview.get_checked_items(true);
			if (!families.length) return frappe.msgprint(__("Select at least one family."));
			email_households(families);
		});
	},
};

// Each household's own email, else its primary contact's, all in BCC so no one sees the others.
function email_households(families) {
	frappe
		.xcall("churchit.church_people.list_actions.get_household_emails", { families })
		.then(({ emails, without_email }) => {
			const note =
				without_email.length &&
				__("No email address for {0}.", [
					without_email.map(frappe.utils.escape_html).join(", "),
				]);
			if (!emails.length) {
				frappe.msgprint(note);
				return;
			}
			if (note) frappe.show_alert({ message: note, indicator: "orange" }, 10);
			const composer = new frappe.views.CommunicationComposer({
				recipients: frappe.session.user_email,
				bcc: emails.join(", "),
			});
			// The composer shows a filled BCC row only once it has loaded, and loading stops early
			// for a user who cannot read Email Account.
			composer.$composer?.find('.email-composer-toggle[data-target="bcc"]').trigger("click");
		});
}
