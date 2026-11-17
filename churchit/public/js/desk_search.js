// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

(function () {
	const search = frappe.search && frappe.search.utils;
	if (!search) return;

	function title_filter(doctype, text) {
		const meta = frappe.get_meta(doctype);
		const field = (meta && meta.show_title_field_in_link && meta.title_field) || "name";
		return { [field]: ["like", "%" + text + "%"] };
	}

	// Frappe filters on the ID, which churchit numbers and hides from its lists.
	if (search.get_search_in_list) {
		const get_search_in_list = search.get_search_in_list.bind(search);
		search.get_search_in_list = function (keywords) {
			const items = get_search_in_list(keywords) || [];
			items.forEach((item) => {
				if (!item.route_options || !item.route_options.name) return;

				const doctype = item.route && item.route[1];
				const text = item.route_options.name[1].slice(1, -1);
				item.onclick = () => {
					frappe.model.with_doctype(doctype, () => {
						frappe.route_options = title_filter(doctype, text);
						frappe.set_route("List", doctype);
					});
				};
				delete item.route_options;
			});
			return items;
		};
	}

	// A churchit sidebar label that differs from its target is a name the search bar does not know.
	const links = [];
	const targets = {};
	Object.entries(frappe.boot.module_sidebars || {}).forEach(([shell, sidebar]) => {
		if (sidebar.app !== "churchit") return;
		(sidebar.items || []).forEach((item) => {
			const key = (item.label || "").toLowerCase();
			if (item.type !== "Link" || item.link_type === "Workspace") return;
			if (!key || key === (item.link_to || "").toLowerCase()) return;

			links.push({ shell, sidebar, item, key });
			targets[key] = (targets[key] || new Set()).add(item.link_to);
		});
	});

	// One label on two different pages, such as Unread Letters, names its sidebar too.
	const labels = new Set();
	links.forEach(({ shell, sidebar, item, key }) => {
		const is_shared = targets[key].size > 1;
		const label = is_shared ? __("{0} ({1})", [item.label, sidebar.label]) : item.label;
		if (labels.has(label.toLowerCase())) return;

		labels.add(label.toLowerCase());
		search.make_function_searchable(() => {
			const route = frappe.ui.sidebar_item.get_route(item, false, shell);
			if (route) frappe.set_route(route);
		}, label);
	});
})();
