// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.listview_settings["Song"] = {
	onload(listview) {
		add_song_import_button(listview);
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
