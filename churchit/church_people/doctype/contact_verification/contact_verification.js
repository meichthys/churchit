// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The Returned Card dialog (churchit.church_people.contact_cards): one person's details as the church
// has them, which the reader changes to match the paper card, then saves. A card's QR code holds this
// form's URL with ?person=, so a phone camera or Scan Card opens the dialog for that person.
const CONTACT_CARDS = "churchit.church_people.contact_cards";
const READ_CARD = "churchit.ai.contact_card_reading.read_card";
const CARD_TABLES = ["emails", "phones", "addresses"];
const CARD_VALUES = [
	"birthday",
	"birthday_year_unknown",
	"anniversary",
	"emergency_contact_name",
	"emergency_contact_phone",
	"texting",
];

frappe.ui.form.on("Contact Verification", {
	refresh(frm) {
		if (frm.is_new() || !frm.has_perm("write")) return;
		frm.add_custom_button(__("Record Returned Card"), () => pick_returned_card(frm));
		frm.add_custom_button(__("Scan Card"), () => scan_contact_card(frm));
		const person = frappe.route_options?.person;
		if (person) {
			delete frappe.route_options.person;
			open_returned_card(frm, person);
		}
	},
});

function pick_returned_card(frm) {
	const people = (frm.doc.people || []).map((row) => row.person);
	const dialog = new frappe.ui.Dialog({
		title: __("Record Returned Card"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "person",
				label: __("Person"),
				options: "Person",
				reqd: 1,
				get_query: () => ({ filters: { name: ["in", people] } }),
			},
		],
		primary_action_label: __("Open Card"),
		primary_action({ person }) {
			dialog.hide();
			open_returned_card(frm, person);
		},
	});
	dialog.show();
}

function scan_contact_card(frm) {
	new frappe.ui.Scanner({
		dialog: true,
		multiple: false,
		on_scan(data) {
			const { verification, person } = read_card_code(data.result.text);
			if (!person) {
				frappe.msgprint(__("This code is not from a contact verification card."));
			} else if (verification && verification !== frm.doc.name) {
				frappe.route_options = { person };
				frappe.set_route("Form", "Contact Verification", verification);
			} else {
				open_returned_card(frm, person);
			}
		},
	});
}

// The Contact Verification and the person in a card's QR code, which is the URL of this form.
function read_card_code(text) {
	try {
		const url = new URL(text, window.location.origin);
		const match = decodeURIComponent(url.pathname).match(/\/contact-verification\/([^/]+)$/);
		return { verification: match?.[1], person: url.searchParams.get("person") };
	} catch (error) {
		return {};
	}
}

function open_returned_card(frm, person) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the Contact Verification first."));
		return;
	}
	frappe
		.xcall(`${CONTACT_CARDS}.get_returned_card`, { verification: frm.doc.name, person }, "GET")
		.then((card) => show_returned_card(frm, card));
}

function show_returned_card(frm, card) {
	const state = { frm, card_photo: card.card_photo };
	const dialog = new frappe.ui.Dialog({
		title: __("Returned Card: {0}", [frappe.utils.escape_html(card.full_name)]),
		size: "extra-large",
		fields: returned_card_fields(card, state),
		primary_action_label: __("Save Card"),
		primary_action(values) {
			save_returned_card(frm, card, state, values, dialog);
		},
	});
	dialog.fields_dict.help.$wrapper.html(
		`<p class="text-muted">${frappe.utils.escape_html(
			__(
				"Change what the person corrected or added on the card, then click Save Card. When the card says everything is right, just click Save Card."
			)
		)}</p>`
	);
	show_card_photo(dialog, state);
	dialog.show();
}

function returned_card_fields(card, state) {
	const shown = new Set(card.shown);
	const fields = [{ fieldtype: "HTML", fieldname: "help" }];
	const table = (fieldname, label, columns) => ({
		fieldtype: "Table",
		fieldname,
		label,
		in_place_edit: true,
		data: (card[fieldname] || []).map((row) => as_grid_row(row)),
		fields: [{ fieldtype: "Data", fieldname: "row", hidden: 1 }, ...columns],
	});
	const column = (fieldtype, fieldname, label, columns, options) => ({
		fieldtype,
		fieldname,
		label,
		columns,
		options,
		in_list_view: 1,
	});
	const remove = column("Check", "remove", __("Remove"), 1);

	if (shown.has("emails"))
		fields.push(
			table("emails", __("Emails"), [
				column("Data", "email_address", __("Email"), 7, "Email"),
				column("Check", "is_primary", __("Main"), 1),
				remove,
			])
		);
	if (shown.has("phones"))
		fields.push(
			table("phones", __("Phones"), [
				column("Data", "phone_number", __("Phone Number"), 5),
				column("Link", "phone_type", __("Type"), 2, "Phone Type"),
				column("Check", "is_primary", __("Main"), 1),
				remove,
			])
		);
	if (shown.has("addresses"))
		fields.push(
			table("addresses", address_table_label(card), [
				column("Data", "address_line1", __("Street"), 3),
				{ fieldtype: "Data", fieldname: "address_line2", label: __("Address Line 2") },
				column("Data", "city", __("City"), 2),
				column("Data", "state", __("State"), 1),
				column("Data", "pincode", __("ZIP Code"), 1),
				{
					fieldtype: "Link",
					fieldname: "country",
					label: __("Country"),
					options: "Country",
					default: frappe.defaults.get_default("country"),
				},
				column("Check", "is_primary", __("Home"), 1),
				column("Check", "is_mailing_address", __("Mailing"), 1),
				remove,
			])
		);
	fields.push(...date_fields(card, shown));
	fields.push(...emergency_contact_fields(card));
	fields.push(...card_fields(card, state));
	return fields;
}

function as_grid_row(row) {
	return { ...row, name: frappe.utils.get_random(10) };
}

function address_table_label(card) {
	return card.address_holder === "Family" ? __("Household Addresses") : __("Addresses");
}

function date_fields(card, shown) {
	const fields = [];
	if (shown.has("birthday"))
		fields.push(
			{
				fieldtype: "Date",
				fieldname: "birthday",
				label: __("Birthday"),
				default: card.birthday,
			},
			{
				fieldtype: "Check",
				fieldname: "birthday_year_unknown",
				label: __("Year Unknown"),
				default: card.birthday_year_unknown,
			}
		);
	if (shown.has("anniversary"))
		fields.push(
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Date",
				fieldname: "anniversary",
				label: __("Anniversary"),
				default: card.anniversary,
			}
		);
	return fields.length ? [{ fieldtype: "Section Break" }, ...fields] : [];
}

function emergency_contact_fields(card) {
	if (!("emergency_contact_name" in card)) return [];
	return [
		{ fieldtype: "Section Break", label: __("Emergency Contact") },
		{
			fieldtype: "Data",
			fieldname: "emergency_contact_name",
			label: __("Name"),
			default: card.emergency_contact_name,
		},
		{ fieldtype: "Column Break" },
		{
			fieldtype: "Data",
			fieldname: "emergency_contact_phone",
			label: __("Phone"),
			options: "Phone",
			default: card.emergency_contact_phone,
		},
	];
}

function texting_fields(card, shown) {
	if (!shown.has("texting")) return [];
	const now = { Yes: __("Yes"), No: __("No") }[card.texting] || __("Not asked yet");
	return [
		{
			fieldtype: "Select",
			fieldname: "texting",
			label: __("May We Text You"),
			options: [
				{ value: "", label: __("No answer") },
				{ value: "Yes", label: __("Yes") },
				{ value: "No", label: __("No") },
			],
			description: __("On file now: {0}", [now]),
		},
	];
}

function card_fields(card, state) {
	const fields = [
		{ fieldtype: "Section Break", label: __("Card") },
		{
			fieldtype: "Date",
			fieldname: "returned_on",
			label: __("Returned On"),
			reqd: 1,
			default: card.returned_on || frappe.datetime.get_today(),
		},
		...texting_fields(card, new Set(card.shown)),
		{ fieldtype: "Small Text", fieldname: "note", label: __("Note"), default: card.note },
		{ fieldtype: "Column Break" },
		{ fieldtype: "HTML", fieldname: "photo" },
		{
			fieldtype: "Button",
			fieldname: "add_photo",
			label: __("Add Card Photo"),
			click: () => add_card_photo(state),
		},
	];
	// The server never sends a card that shows the emergency contact to AI.
	const is_readable = !card.shown.includes("emergency_contact");
	if (is_readable && frappe.boot.churchit?.ai?.on && churchit.ai?.can_run?.()) {
		fields.push({
			fieldtype: "Button",
			fieldname: "read_with_ai",
			label: __("Read Card with AI"),
			click: () => read_card_with_ai(card, state),
		});
	}
	return fields;
}

function add_card_photo(state) {
	new frappe.ui.FileUploader({
		doctype: state.frm.doctype,
		docname: state.frm.docname,
		allow_toggle_private: false,
		restrictions: { allowed_file_types: ["image/*"] },
		on_success(file) {
			state.card_photo = file.file_url;
			show_card_photo(state.dialog, state);
		},
	});
}

function show_card_photo(dialog, state) {
	state.dialog = dialog;
	const url = state.card_photo;
	dialog.fields_dict.photo.$wrapper.html(
		url
			? `<a href="${encodeURI(url)}" target="_blank" rel="noopener"><img src="${encodeURI(
					url
			  )}"
				alt="${frappe.utils.escape_html(__("Card photo"))}"
				style="max-width: 100%; max-height: 16rem; object-fit: contain;"></a>`
			: ""
	);
	dialog.fields_dict.read_with_ai?.$wrapper.toggle(Boolean(url));
}

function read_card_with_ai(card, state) {
	churchit.ai.run_action({
		title: __("Read Card with AI"),
		method: READ_CARD,
		args: {
			verification: state.frm.doc.name,
			person: card.person,
			card_photo: state.card_photo,
		},
		render: (result) => describe_reading(result),
		use_label: __("Fill In the Card"),
		note: __(
			"AI read this from the photo. Check each value against the card before you save."
		),
		on_use: (result) => fill_from_reading(state.dialog, result),
	});
}

function describe_reading(result) {
	const escape = churchit.ai.escape;
	const text = (value) =>
		value && typeof value === "object"
			? Object.values(value).filter(Boolean).join(", ")
			: value;
	const items = [
		...result.lines.map((line) =>
			line.mark === "right"
				? __("{0}: right", [line.value])
				: __("{0}: wrong, {1}", [line.value, text(line.correction) || __("remove it")])
		),
		...result.new_emails.map((row) => __("New email: {0}", [row.email_address])),
		...result.new_phones.map((row) => __("New phone: {0}", [row.phone_number])),
		...result.new_addresses.map((row) => __("New address: {0}", [text(row)])),
	];
	if (result.texting) items.push(__("Texts: {0}", [__(result.texting)]));
	if (!items.length) return `<p>${escape(__("AI found no marks on the card."))}</p>`;
	return `<ul>${items.map((item) => `<li>${escape(item)}</li>`).join("")}</ul>`;
}

// Put what AI read into the open dialog, unsaved: a person checks it and clicks Save Card.
function fill_from_reading(dialog, result) {
	const value_fields = { emails: "email_address", phones: "phone_number" };
	for (const line of result.lines) {
		if (line.mark !== "wrong") continue;
		const row = get_grid_rows(dialog, line.item).find((each) => each.row === line.row);
		if (row && !line.correction) row.remove = 1;
		else if (row && line.item === "addresses") Object.assign(row, line.correction);
		else if (row) row[value_fields[line.item]] = line.correction;
		else if (line.item === "birthday" && line.correction) dialog.set_values(line.correction);
		else if (line.item === "anniversary" && line.correction)
			dialog.set_value("anniversary", line.correction);
	}
	add_grid_rows(dialog, "emails", result.new_emails);
	add_grid_rows(dialog, "phones", result.new_phones);
	add_grid_rows(dialog, "addresses", result.new_addresses);
	if (result.birthday) dialog.set_values(result.birthday);
	if (result.anniversary) dialog.set_value("anniversary", result.anniversary);
	if (result.texting) dialog.set_value("texting", result.texting);
	CARD_TABLES.forEach((fieldname) => dialog.fields_dict[fieldname]?.grid.refresh());
}

function get_grid_rows(dialog, fieldname) {
	return dialog.fields_dict[fieldname]?.df.data || [];
}

function add_grid_rows(dialog, fieldname, rows) {
	const field = dialog.fields_dict[fieldname];
	if (!field || !rows?.length) return;
	field.df.data.push(...rows.map((row) => as_grid_row(row)));
}

function save_returned_card(frm, card, state, values, dialog) {
	const sent = {
		...values,
		modified: card.modified,
		address_holder: card.address_holder,
		address_holder_modified: card.address_holder_modified,
		card_photo: state.card_photo,
	};
	// get_values leaves out an emptied field, which the server must see to clear it.
	for (const fieldname of CARD_VALUES) {
		if (dialog.fields_dict[fieldname]) sent[fieldname] = values[fieldname] ?? "";
	}
	for (const fieldname of CARD_TABLES) {
		if (!(fieldname in card)) continue;
		sent[fieldname] = with_removed_rows(card[fieldname], get_grid_rows(dialog, fieldname));
	}
	frappe
		.xcall(`${CONTACT_CARDS}.record_returned_card`, {
			verification: frm.doc.name,
			person: card.person,
			card: sent,
		})
		.then((status) => {
			dialog.hide();
			frappe.show_alert({
				message: __("{0}: card {1}", [card.full_name, __(status)]),
				indicator: "green",
			});
			frm.reload_doc();
		});
}

// The dialog's rows, plus each saved row that was deleted from the grid, marked Remove.
function with_removed_rows(saved, rows) {
	const kept = new Set(rows.map((row) => row.row).filter(Boolean));
	const removed = saved
		.filter((row) => !kept.has(row.row))
		.map((row) => ({ ...row, remove: 1 }));
	return [...rows, ...removed];
}
