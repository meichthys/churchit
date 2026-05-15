// Copyright (c) 2025, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Person", {
	refresh(frm) {
		// Calculate age from birthday
		if (frm.doc.birthday) {
			const today = frappe.datetime.get_today();
			const birthDate = new Date(frm.doc.birthday);
			const todayDate = new Date(today);

			let age = todayDate.getFullYear() - birthDate.getFullYear();

			if (todayDate.getMonth() < birthDate.getMonth() ||
			    (todayDate.getMonth() === birthDate.getMonth() && todayDate.getDate() < birthDate.getDate())) {
				age--;
			}

			frm.doc.age = age;
			frm.refresh_field('age');
		}

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

		// Add 'Invite to Portal' button if email is provided and no Portal User is linked
		if (frm.doc.email && !frm.doc.user) {
			frm.add_custom_button(__('Invite to Portal'), function () {
				frm.call("invite_to_portal")
			});
		}

		// Add 'Person Tour' button
		frm.add_custom_button(__('Tutorial'), function () {
			frm.tour.init("Person").then(() => frm.tour.start());
		});

	},

	// Set mailing address to home address if "Different Mailing Address" is unchecked
	before_save: function(frm) {
		if (!frm.doc.different_mailing_address) {
			frm.set_value("mailing_address", frm.doc.home_address);
		}
	}

});
