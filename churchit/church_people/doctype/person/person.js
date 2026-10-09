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

		// Add 'New Family From Person' button if Last Name is populated and person does not already head a family
		if (frm.doc.last_name && !(frm.doc.family && frm.doc.is_head_of_household)) {
			frm.add_custom_button(__("New Family From Person"), function () {
				frm.call("new_family_from_person");
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
			show_family_members_without_relation(frm);
		}

		// Add 'Person Tour' button
		frm.add_custom_button(__("Tutorial"), function () {
			frm.tour.init("Person").then(() => frm.tour.start());
		});
	},
});

// Name the family members the Family's 'Relationship to Head' labels could not relate to this person.
function show_family_members_without_relation(frm) {
	if (!frm.doc.family) return;
	frappe.db
		.get_list("Person", {
			filters: { family: frm.doc.family, name: ["!=", frm.doc.name] },
			fields: ["name", "full_name"],
		})
		.then((members) => {
			const related = new Set((frm.doc.relations || []).map((row) => row.person));
			const missing = members.filter((member) => !related.has(member.name));
			if (!missing.length) return;
			const names = missing.map((member) => member.full_name).join(", ");
			frm.dashboard.set_headline_alert(
				__(
					"No relation could be worked out for {0}. Set their Relationship to Head on the Family, or add a Relations row on the Family tab.",
					[frappe.utils.escape_html(names)]
				),
				"yellow"
			);
		});
}

// Show the most recent background check on the form dashboard so leaders can
// see at a glance whether this person is cleared to serve.
function show_background_check_status(frm) {
	frappe.db
		.get_list("Background Check", {
			filters: { person: frm.doc.name },
			fields: ["check_type", "status", "expires_on"],
			order_by: "requested_on desc",
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
