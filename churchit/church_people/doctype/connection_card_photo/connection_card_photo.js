// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// The photo beside the draft that AI read from it (churchit.ai.card_capture), with the people the
// draft may already be. Every value of the draft is the model's text, so it is shown escaped.
const CARD_PHOTO_FIELDS = [
	["first_name", __("First Name")],
	["last_name", __("Last Name")],
	["email", __("Email")],
	["phone", __("Phone")],
	["visit", __("I Am")],
	["how_heard", __("How Did You Hear About Us?")],
	["message", __("Anything Else?")],
];

frappe.ui.form.on("Connection Card Photo", {
	refresh(frm) {
		const draft = get_card_draft(frm);
		render_card_photo(frm);
		render_card_draft(frm, draft);
		render_card_matches(frm, draft);
		add_card_photo_buttons(frm);
	},
});

function get_card_draft(frm) {
	try {
		return frm.doc.draft ? JSON.parse(frm.doc.draft) : null;
	} catch (error) {
		return null;
	}
}

function render_card_photo(frm) {
	const url = frm.doc.photo;
	const html = url
		? `<a href="${encodeURI(url)}" target="_blank" rel="noopener"><img src="${encodeURI(url)}"
			alt="${frappe.utils.escape_html(__("Card photo"))}"
			style="max-width: 100%; max-height: 32rem; object-fit: contain;"></a>`
		: "";
	frm.get_field("photo_html").$wrapper.html(html);
}

function render_card_draft(frm, draft) {
	const wrapper = frm.get_field("draft_html").$wrapper;
	if (!draft) {
		wrapper.html(card_photo_note(frm));
		return;
	}
	const escape = frappe.utils.escape_html;
	const rows = CARD_PHOTO_FIELDS.filter(([fieldname]) => draft[fieldname]).map(
		([fieldname, label]) =>
			`<tr><th class="text-muted">${escape(label)}</th><td>${escape(
				draft[fieldname]
			)}</td></tr>`
	);
	const interests = (draft.interests || []).map((row) => escape(row.interest));
	if (interests.length) {
		rows.push(
			`<tr><th class="text-muted">${escape(__("I Would Like To"))}</th><td>${interests.join(
				", "
			)}</td></tr>`
		);
	}
	const members = (draft.household_members || []).map((row) =>
		escape(
			[row.first_name, row.last_name].filter(Boolean).join(" ") +
				[row.relationship, row.birth_date]
					.filter(Boolean)
					.map((part) => ` (${part})`)
					.join("")
		)
	);
	if (members.length) {
		rows.push(
			`<tr><th class="text-muted">${escape(__("Who Is With You?"))}</th><td>${members.join(
				"<br>"
			)}</td></tr>`
		);
	}
	wrapper.html(`
		<div class="form-message yellow"><div>${escape(
			__("AI draft. Check each value against the photo before you create the card.")
		)}</div></div>
		<table class="table table-sm">${rows.join("")}</table>`);
}

function card_photo_note(frm) {
	const notes = {
		Waiting: __("Waiting for AI to read the photo."),
		Reading: __("AI is reading the photo. A local model can take several minutes."),
	};
	const note = notes[frm.doc.status];
	return note ? `<p class="text-muted">${frappe.utils.escape_html(note)}</p>` : "";
}

function render_card_matches(frm, draft) {
	const wrapper = frm.get_field("matches_html").$wrapper.empty();
	if (!draft || frm.doc.status !== "Ready to Check" || !frappe.model.can_create("Person"))
		return;

	const people = [
		{ ...draft, emails: [draft.email].filter(Boolean), phones: [draft.phone].filter(Boolean) },
		...(draft.household_members || []),
	];
	Promise.all(
		people.map((candidate) =>
			frappe
				.xcall(
					"churchit.church_people.matching.get_possible_matches",
					{ candidate },
					"GET"
				)
				.catch(() => [])
		)
	).then((found) => {
		const lines = people
			.map((person, index) => card_match_line(person, found[index]))
			.filter(Boolean);
		if (!lines.length) return;
		wrapper.html(`
			<p class="text-muted small">${frappe.utils.escape_html(
				__(
					"Possible duplicates. Saving the card links or adds the people as any new card does."
				)
			)}</p>
			<ul>${lines.join("")}</ul>`);
	});
}

function card_match_line(person, matches) {
	if (!matches?.length) return "";
	const escape = frappe.utils.escape_html;
	const name = escape([person.first_name, person.last_name].filter(Boolean).join(" "));
	const links = matches.map((match) => {
		const link = frappe.utils.get_form_link(
			"Person",
			match.person,
			true,
			escape(match.full_name)
		);
		return `${link} (${match.reasons.map((reason) => escape(__(reason))).join(", ")})`;
	});
	return `<li>${name}: ${links.join("; ")}</li>`;
}

function add_card_photo_buttons(frm) {
	if (frm.is_new() || !frm.has_perm("write") || !frappe.boot.churchit?.ai?.on) return;

	if (frm.doc.status === "Ready to Check" && frappe.model.can_create("Connection Card")) {
		frm.add_custom_button(__("Create Connection Card"), () =>
			frappe
				.xcall("churchit.ai.card_capture.create_card", { photo: frm.doc.name })
				.then(({ url }) => {
					const target = new URL(url, window.location.origin);
					frappe.set_route(target.pathname + target.search);
				})
		);
	}
	if (frm.doc.__onload?.is_readable_again && churchit.ai.can_run(true)) {
		frm.add_custom_button(
			__("Read Again"),
			() =>
				frappe
					.xcall("churchit.ai.card_capture.read_again", { photo: frm.doc.name })
					.then(() => frm.reload_doc()),
			__("Actions")
		);
	}
}
