// Adds a visual indicator to form fields that are published on the website.
// The indicator is a small globe badge appended to the field's label area.
// Published field data is fetched once per doctype and cached for the session.

(function () {
	const INDICATOR_CLASS = "published-field-indicator";

	// Session-level cache: doctype → {fieldname: [source, …]}
	const _cache = {};

	function fetch_published_fields(doctype) {
		if (_cache[doctype] !== undefined) {
			return Promise.resolve(_cache[doctype]);
		}
		return frappe
			.xcall("church.church_website.api.get_published_fields", {
				doctype: doctype,
			})
			.then(function (data) {
				_cache[doctype] = data || {};
				return _cache[doctype];
			})
			.catch(function () {
				_cache[doctype] = {};
				return _cache[doctype];
			});
	}

	function apply_indicators(frm, published) {
		// Remove any existing indicators first (in case of re-render)
		frm.$wrapper.find("." + INDICATOR_CLASS).remove();

		for (const fieldname of Object.keys(published)) {
			const field = frm.fields_dict[fieldname];
			if (!field || !field.$wrapper) continue;

			const sources = published[fieldname];
			const titles = sources.map(function (s) { return s.title; });
			const tooltip = __("Shown on web page: {0}", [titles.join(", ")]);
			// Link to the first source's route
			const route = "/" + sources[0].route;

			const $badge = $("<a>")
				.addClass(INDICATOR_CLASS)
				.attr("title", tooltip)
				.attr("href", route)
				.attr("target", "_blank")
				.css({ "margin-left": "6px" })
				.html(
					'<svg class="icon icon-sm" aria-hidden="true">' +
						'<use href="#icon-external-link"></use>' +
						"</svg>"
				);

			// Append to the label area if available
			const $label = field.$wrapper.find(
				".clearfix .label-area, .clearfix label"
			);
			if ($label.length) {
				$label.first().append($badge);
			}
		}
	}

	$(document).on("form-refresh", function (_e, frm) {
		if (!frm || !frm.meta) return;

		// Only apply to church-module doctypes
		const module = frm.meta.module || "";
		if (!module.startsWith("Church")) return;

		fetch_published_fields(frm.doctype).then(function (published) {
			if (published && Object.keys(published).length) {
				apply_indicators(frm, published);
			}
		});
	});
})();
