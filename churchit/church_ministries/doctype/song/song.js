// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Song", {
	refresh(frm) {
		if (frm.is_new()) return;
		add_chord_chart_button(frm);
		add_make_slides_button(frm);
		add_present_button(frm);
		add_export_button(frm);
	},
});

const SONG_METHOD = "churchit.church_ministries.doctype.song.song";

function add_chord_chart_button(frm) {
	const arrangements = get_charted_arrangements(frm);
	if (!arrangements.length) return;
	frm.add_custom_button(__("Chord Chart"), () => {
		if (frm.is_dirty()) return frappe.msgprint(__("Save the song first."));
		const written_key = (name) =>
			arrangements.find((row) => row.arrangement_name === name).song_key ||
			frm.doc.default_key;
		const dialog = new frappe.ui.Dialog({
			title: frappe.utils.escape_html(frm.doc.title),
			size: "large",
			fields: [
				{
					fieldname: "arrangement",
					fieldtype: "Select",
					label: __("Arrangement"),
					options: arrangements.map((row) => as_option(row.arrangement_name)),
					default: arrangements[0].arrangement_name,
					onchange: () => {
						const key = written_key(dialog.get_value("arrangement"));
						dialog.set_df_property("key", "options", get_keys_in_mode_of(key));
						dialog.set_value("key", key).then(show);
					},
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "key",
					fieldtype: "Select",
					label: __("Key"),
					options: get_keys_in_mode_of(written_key(arrangements[0].arrangement_name)),
					default: written_key(arrangements[0].arrangement_name),
					onchange: () => show(),
				},
				{ fieldtype: "Section Break" },
				{ fieldname: "chart", fieldtype: "HTML" },
			],
		});
		const show = frappe.utils.debounce(() => {
			const { arrangement, key } = dialog.get_values(true);
			frappe
				.xcall(
					`${SONG_METHOD}.render_chord_chart`,
					{ song: frm.doc.name, arrangement, key },
					"GET"
				)
				.then((html) => dialog.fields_dict.chart.$wrapper.html(html));
		}, 100);
		dialog.show();
		show();
	});
}

function add_make_slides_button(frm) {
	const names = get_charted_arrangements(frm).map((row) => row.arrangement_name);
	if (!names.length || !frm.has_perm("write")) return;
	frm.add_custom_button(__("Make Slides from ChordPro"), () => {
		if (frm.is_dirty()) return frappe.msgprint(__("Save the song first."));
		if (names.length === 1) return confirm_make_slides(frm, names[0]);
		frappe.prompt(
			{
				fieldname: "arrangement",
				fieldtype: "Select",
				label: __("Arrangement"),
				options: names.map(as_option),
				default: names[0],
				reqd: 1,
			},
			({ arrangement }) => confirm_make_slides(frm, arrangement),
			__("Make Slides from ChordPro"),
			__("Next")
		);
	});
}

function confirm_make_slides(frm, arrangement) {
	const message = __(
		"Replace every slide of this song with one slide for each section of the {0} chart?",
		[frappe.utils.escape_html(arrangement)]
	);
	frappe.confirm(message, () =>
		frappe
			.xcall(`${SONG_METHOD}.make_slides`, { song: frm.doc.name, arrangement })
			.then((count) => {
				frappe.show_alert({
					message: __("{0} slides made.", [count]),
					indicator: "green",
				});
				frm.reload_doc();
			})
	);
}

// A chart moves only to a key of the mode it is written in.
function get_keys_in_mode_of(key) {
	const keys = frappe.meta.get_docfield("Song Arrangement", "song_key").options.split("\n");
	return key
		? keys.filter((option) => option && option.endsWith("m") === key.endsWith("m"))
		: keys;
}

function as_option(name) {
	return { label: frappe.utils.escape_html(name), value: name };
}

function get_charted_arrangements(frm) {
	return (frm.doc.arrangements || []).filter((row) => row.chordpro);
}

function add_present_button(frm) {
	frm.add_custom_button(__("Present"), () => {
		window.open(`/sermon_presentation?song=${encodeURIComponent(frm.doc.name)}`, "_blank");
	});
}

function add_export_button(frm) {
	if (!get_charted_arrangements(frm).length) return;
	frm.add_custom_button(__("Export"), () => {
		if (frm.is_dirty()) return frappe.msgprint(__("Save the song first."));
		frappe.prompt(
			{
				fieldname: "file_format",
				fieldtype: "Select",
				label: __("Format"),
				options: ["OpenLyrics", "ChordPro"],
				default: "OpenLyrics",
				reqd: 1,
				description: __(
					"OpenLyrics opens in FreeShow, OpenLP and Quelea. ChordPro keeps the chords. The export uses the first arrangement with a ChordPro chart."
				),
			},
			({ file_format }) =>
				window.open(
					"/api/method/churchit.church_ministries.songs.song_files.export_songs?" +
						$.param({ songs: JSON.stringify([frm.doc.name]), file_format })
				),
			__("Export Song"),
			__("Export")
		);
	});
}
