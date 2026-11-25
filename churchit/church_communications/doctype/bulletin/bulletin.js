// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Bulletin", {
	setup(frm) {
		frm.set_query("prayer_request", "prayer_requests", () => ({
			filters: {
				visibility: "Whole Church",
				approved_for_list: 1,
				status: ["not in", ["Answered", "Archived", "Closed"]],
			},
		}));
	},

	onload(frm) {
		if (frm.is_new()) {
			fill_defaults(frm, { sections: true });
		}
	},

	refresh(frm) {
		if (frm.doc.publish) {
			frm.set_intro(
				__("Members can download this bulletin from the portal."),
				"blue",
			);
		}
		if (frappe.model.can_write("Bulletin")) {
			frm.add_custom_button(__("Copy from last week"), () =>
				copy_from_last_week(frm),
			);
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("Print Bulletin"), () => {
				// The print opens in a new tab from the saved bulletin, so unsaved changes would be left out.
				if (frm.is_dirty()) {
					frappe.show_alert({
						message: __("Save the bulletin before you print it."),
						indicator: "orange",
					});
					return;
				}
				frappe.utils.print(frm.doctype, frm.doc.name, "Bulletin");
			});
		}
	},

	function(frm) {
		if (frm.doc.function) {
			fill_defaults(frm, { sections: frm.is_new() });
		}
	},
});

function fill_defaults(frm, { sections }) {
	frappe
		.call({
			method: "churchit.church_communications.doctype.bulletin.bulletin.get_defaults",
			type: "GET",
			args: { function: frm.doc.function },
		})
		.then((r) => {
			const defaults = r.message;
			for (const [field, value] of Object.entries(defaults)) {
				if (
					field === "prayer_requests" ||
					(!sections && field.startsWith("show_"))
				)
					continue;
				frm.set_value(field, value);
			}
			if (!frm.doc.function) return;
			frm.clear_table("prayer_requests");
			defaults.prayer_requests.forEach((row) => {
				// The grid shows the request by its title, which a new row has not loaded yet.
				frappe.utils.add_link_title(
					"Prayer Request",
					row.prayer_request,
					row.title,
				);
				frm.add_child("prayer_requests", row);
			});
			frm.refresh_field("prayer_requests");
		});
}

function copy_from_last_week(frm) {
	frappe
		.call({
			method: "churchit.church_communications.doctype.bulletin.bulletin.get_last_week_text",
			type: "GET",
			args: {
				function: frm.doc.function,
				name: frm.is_new() ? null : frm.doc.name,
			},
		})
		.then((r) => {
			const { welcome, announcements } = r.message;
			if (!welcome && !announcements) {
				frappe.show_alert({
					message: __("There is no earlier bulletin."),
					indicator: "orange",
				});
				return;
			}
			const copy = () => {
				frm.set_value({ welcome, announcements });
				frappe.show_alert({
					message: __(
						"Copied the welcome and announcements from the last bulletin.",
					),
					indicator: "green",
				});
			};
			if (frm.doc.welcome || frm.doc.announcements) {
				frappe.confirm(
					__(
						"Replace this bulletin's welcome and announcements with the last bulletin's?",
					),
					copy,
				);
			} else {
				copy();
			}
		});
}
