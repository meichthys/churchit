// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Function", {
	onload(frm) {
		church.set_church_doctype_query(frm, "association_type", "associations");
		church.set_church_doctype_query(frm, "item_type", "schedule");
	},

	refresh: function (frm) {
		// Customize the Sign-Up Items grid: hide my_quantity (irrelevant on Function)
		// and the description column; show quantity_needed and quantity_signed_up.
		const grid = frm.fields_dict.table_cxhh && frm.fields_dict.table_cxhh.grid;
		if (grid) {
			grid.update_docfield_property("quantity_needed", "in_list_view", 1);
			grid.update_docfield_property("quantity_signed_up", "in_list_view", 1);
			grid.update_docfield_property("my_quantity", "in_list_view", 0);
			grid.update_docfield_property("description", "in_list_view", 0);
			grid.set_column_disp("my_quantity", false);
			grid.set_column_disp("description", false);
			// Force re-evaluation of which columns are visible. By default the grid
			// caches `visible_columns` and won't pick up our docfield property changes.
			grid.reset_grid();
		}

		// Populate the virtual quantity_signed_up column for each Sign-Up Item row.
		populate_signed_up_totals(frm);
		show_freely_given_hint(frm);

		// Add template-fill functionality if we have a template specified and this is a new form
		if (frm.is_new() && frm.doc.type) {
			frappe.db.get_value("Function Type", frm.doc.type, "template_function").then((r) => {
				if (!r.message?.template_function) return;
				// Add 	Fill from Template` button if template exists
				frm.add_custom_button(__("Fill from Template"), function () {
					if (!frm.doc.start_date) {
						frappe.msgprint(
							__("Set the Start Date first, so the schedule moves to it.")
						);
						return;
					}
					frappe.call({
						method: "churchit.church_ministries.doctype.function.function.apply_template",
						args: {
							source_name: r.message.template_function,
							start_date: frm.doc.start_date,
						},
						callback: function (r) {
							if (!r.message) return;
							Object.keys(r.message).forEach((fieldname) => {
								frm.set_value(fieldname, r.message[fieldname]);
							});

							// Fetch link titles for person IDs so the attendance grid
							// displays names instead of IDs (e.g. "John Smith" not "PRSN-0011")
							const personIds = [
								...new Set(
									(r.message.attendance || [])
										.map((a) => a.person)
										.filter(Boolean)
								),
							];
							if (personIds.length) {
								Promise.all(
									personIds.map((id) =>
										frappe.utils.fetch_link_title("Person", id)
									)
								).then(() => frm.refresh_field("attendance"));
							}

							frappe.msgprint({
								message: __("Template applied successfully"),
								indicator: "green",
								alert: true,
							});
						},
					});
				});
			});
		}

		if (!frm.is_new()) {
			frm.add_custom_button(__("Check-In Station"), function () {
				frappe.route_options = { function: frm.doc.name };
				frappe.set_route("check-in");
			});
		}

		// Allow booking rooms and equipment for this saved function (each Room Booking links back to it)
		if (!frm.is_new()) {
			frm.add_custom_button(__("Book a Room"), () => book_rooms(frm), __("Create"));

			frm.add_custom_button(
				__("Bulletin"),
				function () {
					frappe.new_doc("Bulletin", { function: frm.doc.name });
				},
				__("Create")
			);

			frm.add_custom_button(
				__("Schedule"),
				function () {
					frappe.set_route("query-report", "Ministry Team Schedule", {
						function: frm.doc.name,
					});
				},
				__("Ministry Team")
			);

			frm.add_custom_button(
				__("Email the Team"),
				() => email_the_team(frm),
				__("Ministry Team")
			);
		}

		// Add Sign Ups buttons if sign-ups are enabled, there are items, or there are linked sign-ups
		if (!frm.is_new()) {
			const has_items = frm.doc.table_cxhh && frm.doc.table_cxhh.length > 0;

			frappe.db
				.count("Function Sign-Up", {
					filters: { function: frm.doc.name },
				})
				.then((count) => {
					if (frm.doc.allow_sign_ups || has_items || count > 0) {
						frm.add_custom_button(
							__("Show Signed-Up Items"),
							function () {
								frappe.set_route("query-report", "Function Sign-Up Items", {
									function: frm.doc.name,
								});
							},
							__("Sign Ups")
						);

						frm.add_custom_button(
							__("Show Signed-Up People"),
							function () {
								frappe.set_route("list", "Function Sign-Up", {
									function: frm.doc.name,
								});
							},
							__("Sign Ups")
						);
					}
				});
		}
	},

	type: function (frm) {
		// Refresh form to re-evaluate button visibility
		frm.trigger("refresh");
	},
});

// Set default attendance_type on new attendance child rows
frappe.ui.form.on("Function Attendance", {
	attendance_add(frm, cdt, cdn) {
		frappe.db
			.get_value("Function Attendance Type", { type: "Confirmed" }, "name")
			.then((r) => {
				if (r.message?.name) {
					frappe.model.set_value(cdt, cdn, "attendance_type", r.message.name);
				}
			});
	},
});

function email_the_team(frm) {
	frappe
		.xcall(
			"churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment.get_team_emails",
			{ function: frm.doc.name }
		)
		.then(({ emails, without_email }) => {
			if (without_email.length) {
				frappe.show_alert(
					{
						message: __("No email address for {0}", [
							without_email.map(frappe.utils.escape_html).join(", "),
						]),
						indicator: "orange",
					},
					10
				);
			}
			if (!emails.length) {
				frappe.msgprint(
					__("No one asked to serve at this function has an email address.")
				);
				return;
			}
			// The team goes in BCC, so no one sees the others' addresses.
			const composer = new frappe.views.CommunicationComposer({
				doc: frm.doc,
				frm: frm,
				subject: frm.doc.title,
				recipients: frappe.session.user_email,
				bcc: emails.join(", "),
			});
			composer.$composer?.find('.email-composer-toggle[data-target="bcc"]').trigger("click");
		});
}

function book_rooms(frm) {
	let start_datetime = null,
		end_datetime = null;
	if (frm.doc.start_date) {
		const start_time = frm.doc.all_day ? "00:00:00" : frm.doc.start_time || "00:00:00";
		start_datetime = frm.doc.start_date + " " + start_time;
		const end_date = frm.doc.end_date || frm.doc.start_date;
		const end_time = frm.doc.all_day ? "23:59:59" : frm.doc.end_time;
		if (end_time) {
			end_datetime = end_date + " " + end_time;
		}
		// Room Booking requires end > start; default to a 1-hour slot otherwise
		if (!end_datetime || end_datetime <= start_datetime) {
			end_datetime = frappe.datetime.add_to_date(start_datetime, { hours: 1 });
		}
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Book a Room"),
		fields: [
			{
				fieldname: "rooms",
				fieldtype: "MultiSelectList",
				label: __("Rooms"),
				description: __(
					"Each room gets its own booking. Book a room that asks questions on its own Room Booking form."
				),
				get_data: (txt) =>
					frappe.db.get_link_options("Room", txt, {
						is_bookable: 1,
						question_set: ["is", "not set"],
					}),
			},
			{
				fieldname: "assets",
				fieldtype: "MultiSelectList",
				label: __("Equipment"),
				description: __(
					"Booked with the first room that is booked, or alone when you choose no room."
				),
				get_data: (txt) =>
					frappe.db.get_link_options("Church Asset", txt, { is_bookable: 1 }),
			},
			{
				fieldname: "requester",
				fieldtype: "Link",
				options: "Person",
				label: __("Requester"),
				reqd: 1,
			},
			{
				fieldname: "purpose",
				fieldtype: "Data",
				label: __("Purpose"),
				reqd: 1,
				default: frm.doc.function_name || frm.doc.type,
			},
			{
				fieldname: "start_datetime",
				fieldtype: "Datetime",
				label: __("Start"),
				reqd: 1,
				default: start_datetime,
			},
			{
				fieldname: "end_datetime",
				fieldtype: "Datetime",
				label: __("End"),
				reqd: 1,
				default: end_datetime,
			},
		],
		primary_action_label: __("Book"),
		primary_action: (values) => insert_room_bookings(frm, dialog, values),
	});
	dialog.show();
	frappe.db.get_value("Person", { user: frappe.session.user }, "name").then((r) => {
		if (r.message && !dialog.get_value("requester")) {
			dialog.set_value("requester", r.message.name);
		}
	});
}

// One normal insert per room, so permissions and every booking check run on the server.
async function insert_room_bookings(frm, dialog, values) {
	const rooms = values.rooms || [];
	const assets = (values.assets || []).map((asset) => ({ asset }));
	if (!rooms.length && !assets.length) {
		frappe.msgprint(__("Choose a room or some equipment to book."));
		return;
	}
	dialog.hide();
	const made = [];
	for (const room of rooms.length ? rooms : [null]) {
		try {
			made.push(
				await frappe.db.insert({
					doctype: "Room Booking",
					room: room,
					assets: made.length ? [] : assets,
					function: frm.doc.name,
					requester: values.requester,
					purpose: values.purpose,
					start_datetime: values.start_datetime,
					end_datetime: values.end_datetime,
				})
			);
		} catch (e) {
			// The server's message is on screen; book the other rooms.
		}
	}
	if (made.length) {
		frappe.show_alert(
			{
				message: __("Booked: {0}", [
					made
						.map((booking) =>
							frappe.utils.get_form_link(
								"Room Booking",
								booking.name,
								true,
								`${booking.name} (${__(booking.status)})`
							)
						)
						.join(", "),
				]),
				indicator: "green",
			},
			10
		);
	}
}

function populate_signed_up_totals(frm) {
	if (frm.is_new() || !frm.doc.name || !(frm.doc.table_cxhh || []).length) return;
	frappe.call({
		method: "churchit.church_ministries.doctype.function_sign_up.function_sign_up.get_function_item_totals",
		args: { function: frm.doc.name },
		callback: function (r) {
			if (!r.message) return;
			(frm.doc.table_cxhh || []).forEach((row) => {
				const data = r.message[row.item];
				if (!data) return;
				row.quantity_signed_up = data.quantity_signed_up;
			});
			frm.refresh_field("table_cxhh");
		},
	});
}

// A priced function is the place to remember Matthew 10:8, and one click makes it free.
const FREELY_GIVEN = "Freely Given";

frappe.ui.form.on("Function", {
	selections_remove: show_freely_given_hint,
	table_cxhh_remove: show_freely_given_hint,
	discounts_remove: show_freely_given_hint,
});
frappe.ui.form.on("Function Sign-Up Selection", { price: show_freely_given_hint });
frappe.ui.form.on("Function Sign-Up Item", { price: show_freely_given_hint });
frappe.ui.form.on("Function Sign-Up Discount", {
	kind: show_freely_given_hint,
	amount: show_freely_given_hint,
	percent: show_freely_given_hint,
	valid_until: show_freely_given_hint,
});

function show_freely_given_hint(frm) {
	// Function Sign-Up uses the Sign-Up Item table too, and these handlers run on every form.
	if (frm.doctype !== "Function") return;
	const label = __("Offer It Freely");
	frm.remove_custom_button(label);
	const priced = [...(frm.doc.selections || []), ...(frm.doc.table_cxhh || [])].some(
		(row) => flt(row.price) > 0
	);
	if (!priced) {
		frm.set_intro("");
		return;
	}
	const given = (frm.doc.discounts || []).some(
		(row) =>
			row.kind === FREELY_GIVEN &&
			flt(row.percent) >= 100 &&
			!flt(row.amount) &&
			!row.valid_until
	);
	if (given) {
		frm.set_intro(__("This function is freely given: its sign-ups pay nothing."), "green");
		return;
	}
	frm.set_intro(
		`<i>${__("Freely you have received; freely give.")}</i> (Matthew 10:8) ` +
			__(
				"This function has a price. Consider offering it freely: {0} adds a discount that takes the whole price off, and the prices still show what it costs.",
				[`<b>${label}</b>`]
			),
		"blue"
	);
	if (!frm.has_perm("write")) return;
	frm.add_custom_button(label, () => {
		frm.add_child("discounts", { kind: FREELY_GIVEN, percent: 100 });
		frm.refresh_field("discounts");
		frm.save();
	});
}
