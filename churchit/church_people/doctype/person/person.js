// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Person", {
	refresh(frm) {
		// Calculate marriage years from anniversary
		if (frm.doc.anniversary) {
			const today = frappe.datetime.get_today();
			const anniversary = frm.doc.anniversary;
			const anniversaryDate = new Date(anniversary);
			const todayDate = new Date(today);

			let years = todayDate.getFullYear() - anniversaryDate.getFullYear();

			if (todayDate.getMonth() < anniversaryDate.getMonth() ||
			    (todayDate.getMonth() === anniversaryDate.getMonth() && todayDate.getDate() < anniversaryDate.getDate())) {
				years--;
			}

			frm.doc.marriage_years = years;
			frm.refresh_field('marriage_years');
		}

		// Add 'New Family From Person' button if Last Name is populated and person is not already in a family
		if (frm.doc.last_name && !frm.doc.family) {
			frm.add_custom_button(__('New Family From Person'), function () {
				frm.call("new_family_from_person")
			})
		}

		// Add 'Invite to Portal' button if an email is on file and no Portal User is linked
		const has_email = (frm.doc.emails || []).some((row) => row.email_address);
		if (has_email && !frm.doc.user) {
			frm.add_custom_button(__('Invite to Portal'), function () {
				frm.call("invite_to_portal")
			});
		}

		// Add 'Person Tour' button
		frm.add_custom_button(__('Tutorial'), function () {
			frm.tour.init("Person").then(() => frm.tour.start());
		});

	}

});
