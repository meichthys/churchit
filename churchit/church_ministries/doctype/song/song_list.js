// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Song"] = {
	onload(listview) {
		add_song_import_button(listview);
		add_public_domain_hymns_button(listview);
		add_song_export_list_button(listview);
	},
};

const SONG_FILES = "churchit.church_ministries.songs.song_files";
const items = (rows) => `<ul>${rows.map((row) => `<li>${row}</li>`).join("")}</ul>`;

function add_song_import_button(listview) {
	if (!frappe.model.can_create("Song")) return;
	listview.page.add_inner_button(__("Import Song Files"), () => {
		const files = [];
		const uploader = new frappe.ui.FileUploader({
			dialog_title: __("Import Song Files"),
			allow_multiple: true,
			allow_toggle_private: false,
			disable_file_browser: true,
			allow_web_link: false,
			allow_take_photo: false,
			allow_google_drive: false,
			restrictions: {
				allowed_file_types: [".cho", ".chordpro", ".chopro", ".pro", ".usr"],
				max_file_size: 1024 * 1024,
				max_number_of_files: 50,
			},
			on_success: (file) => file && files.push(file.name),
		});
		uploader.dialog.set_primary_action(__("Import"), () =>
			uploader.upload_files().then(() => import_song_files(listview, files))
		);
	});
}

function import_song_files(listview, files) {
	const escape = frappe.utils.escape_html;
	frappe.xcall(`${SONG_FILES}.import_song_files`, { files }).then(({ imported, skipped }) => {
		listview.refresh();
		const links = imported.map(
			(row) =>
				`<a href="${frappe.utils.get_form_link("Song", row.song)}">${escape(row.file)}</a>`
		);
		let message = __("{0} songs imported.", [imported.length]) + items(links);
		if (skipped.length) {
			const reason = __(
				"{0} files skipped: a song with the same CCLI number or title is listed.",
				[skipped.length]
			);
			message += reason + items(skipped.map(escape));
		}
		frappe.msgprint({ title: __("Import Song Files"), message, indicator: "green" });
	});
}

function add_public_domain_hymns_button(listview) {
	if (!frappe.model.can_create("Song")) return;
	listview.page.add_inner_button(__("Add Public-Domain Hymns"), () =>
		frappe
			.xcall(`${SONG_FILES}.get_public_domain_hymns`, {}, "GET")
			.then((hymns) => choose_public_domain_hymns(listview, hymns))
	);
}

function choose_public_domain_hymns(listview, hymns) {
	const escape = frappe.utils.escape_html;
	const titles = Object.fromEntries(hymns.map((hymn) => [hymn.file, escape(hymn.title)]));
	const options = hymns.map((hymn) => {
		const authors = `<span class="text-muted">${escape(hymn.authors)}</span>`;
		return { value: hymn.file, label: `${titles[hymn.file]} ${authors}` };
	});
	const dialog = new frappe.ui.Dialog({
		title: __("Add Public-Domain Hymns"),
		size: "large",
		fields: [
			{
				fieldname: "files",
				fieldtype: "MultiCheck",
				label: __("Hymns"),
				description: __(
					"Words and music published in 1930 or earlier. Each hymn becomes a public-domain song with its chord chart and slides. A hymn whose title your song list already shows is skipped."
				),
				select_all: 1,
				columns: 2,
				options,
			},
		],
		primary_action_label: __("Add"),
		primary_action: ({ files }) => {
			if (!files?.length) return frappe.msgprint(__("Select at least one hymn."));
			return frappe
				.xcall(`${SONG_FILES}.add_public_domain_hymns`, { files }, "POST", {
					freeze: true,
				})
				.then((result) => {
					dialog.hide();
					listview.refresh();
					show_hymns_added(titles, result);
				});
		},
	});
	dialog.show();
}

function show_hymns_added(titles, { imported, skipped }) {
	const links = imported.map(
		(row) =>
			`<a href="${frappe.utils.get_form_link("Song", row.song)}">${titles[row.file]}</a>`
	);
	let message = __("{0} hymns added.", [imported.length]) + items(links);
	if (skipped.length) {
		const reason = __("{0} hymns skipped: a song with the same title is listed.", [
			skipped.length,
		]);
		message += reason + items(skipped.map((file) => titles[file]));
	}
	frappe.msgprint({ title: __("Add Public-Domain Hymns"), message, indicator: "green" });
}

function add_song_export_list_button(listview) {
	listview.page.add_action_item(__("Export Songs"), () => {
		const songs = listview.get_checked_items(true);
		if (!songs.length) return frappe.msgprint(__("Select at least one song."));
		frappe.prompt(
			{
				fieldname: "file_format",
				fieldtype: "Select",
				label: __("Format"),
				options: ["OpenLyrics", "ChordPro"],
				default: "OpenLyrics",
				reqd: 1,
				description: __(
					"OpenLyrics opens in FreeShow, OpenLP and Quelea. ChordPro keeps the chords. More than one song comes as a zip file."
				),
			},
			({ file_format }) =>
				window.open(
					`/api/method/${SONG_FILES}.export_songs?` +
						$.param({ songs: JSON.stringify(songs), file_format })
				),
			__("Export Songs"),
			__("Export")
		);
	});
}
