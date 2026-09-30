// Adds a visual indicator to form fields that are shown on the website.
// The indicator is a small badge appended to the field's label area, linking
// to the page that shows it. The whole map is fetched once per session.

(function () {
	const INDICATOR_CLASS = "published-field-indicator";
	const MANAGER_ROLES = ["Church Manager", "System Manager"];
	// A field anyone can see keeps the outgoing-link badge; one only the portal
	// shows gets the people badge.
	const PUBLIC_ICON = "icon-external-link";
	const MEMBERS_ICON = "icon-users";

	// Session-level cache: a promise of {doctype: {fieldname: [source, …]}}
	let _published = null;

	function fetch_published_fields() {
		if (!_published) {
			_published = frappe
				.xcall("churchit.church_website.api.get_published_fields")
				.then(function (data) {
					return data || {};
				})
				.catch(function () {
					return {};
				});
		}
		return _published;
	}

	function describe(open_to_all, members_only) {
		const titles = (sources) => sources.map((s) => s.title).join(", ");
		const lines = [];
		if (open_to_all.length) {
			lines.push(__("Shown on the public website: {0}", [titles(open_to_all)]));
		}
		if (members_only.length) {
			lines.push(__("Shown to signed-in members: {0}", [titles(members_only)]));
		}
		return lines.join("\n");
	}

	function apply_indicators(frm, published) {
		// Remove any existing indicators first (in case of re-render)
		frm.$wrapper.find("." + INDICATOR_CLASS).remove();

		for (const fieldname of Object.keys(published)) {
			const field = frm.fields_dict[fieldname];
			if (!field || !field.$wrapper) continue;

			const sources = published[fieldname];
			const open_to_all = sources.filter((s) => s.access !== "members");
			const tooltip = describe(
				open_to_all,
				sources.filter((s) => s.access === "members")
			);
			// Link to a page anyone can open when there is one, else the first source.
			const route = "/" + (open_to_all[0] || sources[0]).route;
			const icon = open_to_all.length ? PUBLIC_ICON : MEMBERS_ICON;

			const $badge = $("<a>")
				.addClass(INDICATOR_CLASS)
				.attr("title", tooltip)
				.attr("href", route)
				.attr("target", "_blank")
				.css({ "margin-left": "6px" })
				.html(
					'<svg class="icon icon-sm" aria-hidden="true">' +
						`<use href="#${icon}"></use>` +
						"</svg>"
				);

			// Append to the label area if available
			const $label = field.$wrapper.find(".clearfix .label-area, .clearfix label");
			if ($label.length) {
				$label.first().append($badge);
			}
		}
	}

	$(document).on("form-refresh", function (_e, frm) {
		if (!frm || !frm.meta) return;

		// Only managers may ask where a field is published.
		if (!MANAGER_ROLES.some((role) => frappe.user_roles.includes(role))) return;

		fetch_published_fields().then(function (published) {
			apply_indicators(frm, published[frm.doctype] || {});
		});
	});
})();
