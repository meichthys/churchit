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
				.xcall("churchit.church_website.api.get_published_fields", {}, "GET")
				.then(function (data) {
					return data || {};
				})
				.catch(function () {
					return {};
				});
		}
		return _published;
	}

	function describe(open_to_all, members_only, link_holders) {
		const titles = (sources) => sources.map((s) => s.title).join(", ");
		const lines = [];
		if (open_to_all.length) {
			lines.push(__("Shown on the public website: {0}", [titles(open_to_all)]));
		}
		if (members_only.length) {
			lines.push(__("Shown to signed-in members: {0}", [titles(members_only)]));
		}
		if (link_holders.length) {
			lines.push(__("Shown to whoever opens an emailed link: {0}", [titles(link_holders)]));
		}
		return lines.join("\n");
	}

	// A touch screen has no hover, so the first tap shows the text and its link.
	// It opens above the badge, so it never covers the input under the label.
	function show_on_first_tap($badge, tooltip, route) {
		const $content = $("<div>");
		tooltip.split("\n").forEach((line) => $("<div>").text(line).appendTo($content));
		$("<a target='_blank'>").attr("href", route).text(__("Open page")).appendTo($content);

		$badge.removeAttr("title").attr("aria-label", tooltip).popover({
			trigger: "click",
			placement: "top",
			container: "body",
			html: true,
			content: $content,
		});
		$badge.attr("href", "#").on("click", (event) => event.preventDefault());
	}

	// A tap outside the open badge closes its text.
	$(document).on("click", (event) => {
		const $target = $(event.target);
		if ($target.closest(".popover").length) return;
		$("." + INDICATOR_CLASS)
			.not($target.closest("." + INDICATOR_CLASS))
			.popover("hide");
	});

	// The text sits in body, so it would stay over the next page.
	frappe.router.on("change", () => $("." + INDICATOR_CLASS).popover("hide"));

	function apply_indicators(frm, published) {
		// Remove any existing indicators first (in case of re-render)
		frm.$wrapper
			.find("." + INDICATOR_CLASS)
			.popover("dispose")
			.remove();

		for (const fieldname of Object.keys(published)) {
			const field = frm.fields_dict[fieldname];
			if (!field || !field.$wrapper) continue;

			const sources = published[fieldname];
			const open_to_all = sources.filter((s) => s.access === "public");
			const tooltip = describe(
				open_to_all,
				sources.filter((s) => s.access === "members"),
				sources.filter((s) => s.access === "link holders")
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
				.toggleClass("published-field-touch", frappe.is_mobile())
				.html(
					'<svg class="icon icon-sm" aria-hidden="true">' +
						`<use href="#${icon}"></use>` +
						"</svg>"
				);

			if (frappe.is_mobile()) show_on_first_tap($badge, tooltip, route);

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
