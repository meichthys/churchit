// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.pages["rolodex"].on_page_load = function (wrapper) {
	wrapper.rolodex = new Rolodex(wrapper);
};

frappe.pages["rolodex"].on_page_show = function (wrapper) {
	wrapper.rolodex?.measure();
	wrapper.rolodex?.apply_route_options();
};

const API = "churchit.church_people.page.rolodex.rolodex";
const ADD_TO_GROUP_API = "churchit.church_people.doctype.group.group.add_people";
const LETTERS = [..."ABCDEFGHIJKLMNOPQRSTUVWXYZ", "#"];
const NO_STATUS = "__none__";
const DESKTOP = "(min-width: 992px)";
// Some email apps cut a mailto link off at around 2000 characters.
const MAILTO_LIMIT = 1800;

const ICONS = {
	search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
	filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
	phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
	text: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
	email: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
	map: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
	bookmark: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
	print: '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
	group: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
	open: '<path d="M15 3h6v6M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
	chevron: '<path d="m18 15-6-6-6 6"/>',
	x: '<path d="M18 6 6 18M6 6l12 12"/>',
};

class Rolodex {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Rolodex"),
			single_column: true,
		});
		this.view = "people";
		this.query = "";
		this.filters = {
			church: new Set(),
			status: new Set(),
			group: new Set(),
			position: new Set(),
		};
		this.set_saved([]);
		this.flipped = new Set();
		this.make();
		this.load();
	}

	make() {
		this.page.add_menu_item(__("People List"), () => frappe.set_route("List", "Person"));
		this.$root = $(rolodex_html()).appendTo(this.page.body);
		this.$search = this.$root.find(".rolodex-search input");
		this.$cards = this.$root.find(".rolodex-cards");
		this.$rail = this.$root.find(".rolodex-rail");
		this.$facets = this.$root.find(".rolodex-facets");
		this.$chips = this.$root.find(".rolodex-chips");
		this.$tray = this.$root.find(".rolodex-tray");
		this.$root.find('[data-action="add-to-group"]').toggle(frappe.model.can_write("Group"));
		this.bind();
		this.bind_rail();
		// The desk sidebar can fold away without the window resizing, so watch the page itself.
		const observer = new ResizeObserver(frappe.utils.debounce(() => this.measure(), 50));
		observer.observe(this.$root[0]);
		observer.observe(this.$tray[0]);
	}

	bind() {
		this.$search.on(
			"input",
			frappe.utils.debounce(() => {
				this.query = this.$search.val().trim().toLowerCase();
				this.render();
			}, 120)
		);
		this.$root.on("click", "[data-action]", (e) =>
			this.run_action(e.currentTarget.dataset.action)
		);
		this.$root.on("click", "[data-view]", (e) => this.set_view(e.currentTarget.dataset.view));
		this.$facets.on("change", "input[type=checkbox]", (e) =>
			this.set_filter(
				e.target.closest("[data-facet]").dataset.facet,
				e.target.value,
				e.target.checked
			)
		);
		this.$facets.on("input", ".rolodex-facet-find", (e) => {
			const text = e.target.value.trim().toLowerCase();
			for (const label of $(e.target).siblings(".rolodex-options").find("label")) {
				label.toggleAttribute("hidden", !label.textContent.toLowerCase().includes(text));
			}
		});
		this.$chips.on("click", ".rolodex-chip", (e) => {
			const { facet, value } = e.currentTarget.dataset;
			this.set_filter(facet, value, false);
		});
		this.$cards.on("click", "[data-save]", (e) => {
			e.stopPropagation();
			this.toggle_saved([e.currentTarget.dataset.save]);
		});
		this.$cards.on("click", "[data-save-family]", (e) => {
			e.stopPropagation();
			this.toggle_saved(
				this.members_of[e.currentTarget.dataset.saveFamily].map((p) => p.name)
			);
		});
		this.$cards.on("click", "a", (e) => e.stopPropagation());
		this.$cards.on("click", ".rolodex-open", (e) => {
			if (e.ctrlKey || e.metaKey || e.shiftKey) return;
			e.preventDefault();
			frappe.set_route(
				"Form",
				e.currentTarget.dataset.doctype,
				e.currentTarget.dataset.name
			);
		});
		this.$cards.on("click", ".rolodex-card", (e) => this.flip(e.currentTarget));
		this.$cards.on("keydown", ".rolodex-card", (e) => {
			if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) {
				e.preventDefault();
				this.flip(e.currentTarget);
			}
		});
		this.$tray.on("click", ".rolodex-tray-toggle", () => this.toggle_tray());
		this.$tray.on("click", "[data-unsave]", (e) =>
			this.toggle_saved([e.currentTarget.dataset.unsave])
		);
		this.$tray.on("click", "[data-jump]", (e) =>
			this.jump_to_card(e.currentTarget.dataset.jump)
		);
		$(document).on("keydown", (e) => {
			if (e.key === "Escape" && this.is_sheet_open()) this.toggle_filters(false);
		});
	}

	// The rail follows a finger or a held mouse button, like scrubbing a phone's contact list.
	bind_rail() {
		let scrubbing = false;
		const jump_at = (event) => {
			const button = document
				.elementFromPoint(event.clientX, event.clientY)
				?.closest("[data-letter]");
			if (button && !button.disabled) this.jump_to_letter(button.dataset.letter, scrubbing);
		};
		this.$rail.on("pointerdown", (e) => {
			scrubbing = true;
			e.currentTarget.setPointerCapture(e.originalEvent.pointerId);
			jump_at(e.originalEvent);
		});
		this.$rail.on("pointermove", (e) => scrubbing && jump_at(e.originalEvent));
		this.$rail.on("pointerup pointercancel", () => {
			scrubbing = false;
			this.$rail.find(".rolodex-rail-bubble").prop("hidden", true);
		});
		// Pointer presses are handled above; a click with no pointer came from the keyboard.
		this.$rail.on("click", "[data-letter]", (e) => {
			if (!e.originalEvent.detail)
				this.jump_to_letter(e.currentTarget.dataset.letter, false);
		});
	}

	load() {
		this.$cards.html(`<div class="rolodex-empty">${__("Loading…")}</div>`);
		frappe.xcall(`${API}.get_directory`).then((directory) => {
			this.set_directory(directory);
			this.apply_settings(directory.settings);
			this.render_facets();
			this.render();
			this.render_tray();
			this.apply_route_options();
		});
	}

	// The Person and Family lists open the Rolodex in their own view. Read once the
	// directory is in, and only then cleared, so a first visit does not lose it.
	apply_route_options() {
		if (!this.people) return;
		const wanted = frappe.route_options && frappe.route_options.view;
		frappe.route_options = null;
		if (["people", "households"].includes(wanted) && wanted !== this.view)
			this.set_view(wanted);
	}

	set_directory({ people, families, choices }) {
		this.choices = choices;
		this.families = Object.fromEntries(families.map((family) => [family.name, family]));
		this.group_titles = Object.fromEntries(choices.group);
		this.people = people
			.map((person) => {
				const family_title = this.families[person.family]?.family_name || "";
				const text = [person.full_name, family_title, person.email]
					.join(" ")
					.toLowerCase();
				const key = sort_key(person.last_name || person.first_name || person.full_name);
				return { ...person, family_title, search_text: text, sort_key: key };
			})
			.sort(
				(a, b) => compare(a.sort_key, b.sort_key) || compare(a.first_name, b.first_name)
			);
		this.by_name = Object.fromEntries(this.people.map((person) => [person.name, person]));
		this.members_of = {};
		for (const person of this.people) {
			if (person.family) (this.members_of[person.family] ||= []).push(person);
		}
		for (const members of Object.values(this.members_of)) {
			members.sort((a, b) => b.is_head_of_household - a.is_head_of_household);
		}
	}

	apply_settings(settings) {
		this.set_saved((settings.saved || []).filter((name) => this.by_name[name]));
		this.view = settings.view === "households" ? "households" : "people";
		this.mark_view();
		this.filters_open = settings.filters_open !== false;
		if (window.matchMedia(DESKTOP).matches) this.toggle_filters(this.filters_open, false);
	}

	save_settings() {
		clearTimeout(this.settings_timer);
		const settings = { saved: this.saved, view: this.view, filters_open: this.filters_open };
		this.settings_timer = setTimeout(
			() => frappe.xcall(`${API}.save_settings`, settings),
			400
		);
	}

	matches(person) {
		const { church, status, group, position } = this.filters;
		return (
			this.matches_query(person) &&
			(!church.size || church.has(person.church)) &&
			(!status.size || status.has(person.membership_status || NO_STATUS)) &&
			(!group.size || person.groups.some((name) => group.has(name))) &&
			(!position.size || person.positions.some((name) => position.has(name)))
		);
	}

	matches_query(person) {
		if (!this.query) return true;
		const digits = this.query.replace(/\D/g, "");
		if (digits.length >= 3 && !/[a-z]/.test(this.query)) {
			return (person.phone || "").replace(/\D/g, "").includes(digits);
		}
		return this.query.split(/\s+/).every((word) => person.search_text.includes(word));
	}

	render() {
		this.shown = this.people.filter((person) => this.matches(person));
		const units =
			this.view === "households"
				? this.household_units()
				: this.shown.map((person) => ({ key: person.sort_key, person }));
		const sections = by_letter(units);
		this.$cards.html(
			sections.length
				? sections.map(([letter, items]) => this.section_html(letter, items)).join("")
				: this.empty_html()
		);
		this.render_rail(new Set(sections.map(([letter]) => letter)));
		this.render_chips();
		this.render_count(units);
		this.measure();
	}

	// A household shows when any of its people match, with the others dimmed.
	household_units() {
		const matched = new Set(this.shown.map((person) => person.name));
		const units = new Map();
		for (const person of this.shown) {
			const family = this.families[person.family];
			if (!family) {
				units.set(person.name, { key: person.sort_key, person });
			} else if (!units.has(family.name)) {
				const key = sort_key(family.family_name.split(" - ")[0]);
				units.set(family.name, {
					key,
					family,
					members: this.members_of[family.name],
					matched,
				});
			}
		}
		return [...units.values()].sort((a, b) => compare(a.key, b.key));
	}

	section_html(letter, units) {
		const cards = units.map((unit) =>
			unit.family ? this.household_html(unit) : this.card_html(unit.person)
		);
		return `<section class="rolodex-section" data-letter="${letter}">
			<h2 class="rolodex-letter"><span>${letter}</span></h2>
			<div class="rolodex-grid">${cards.join("")}</div>
		</section>`;
	}

	card_html(person) {
		const e = frappe.utils.escape_html;
		const sub = [person.family_title, person.membership_status]
			.filter(Boolean)
			.map(e)
			.join(" · ");
		const lines = [person.phone, person.email]
			.filter(Boolean)
			.map((line) => `<div>${e(line)}</div>`);
		return `<article class="${this.card_classes(person.name, this.saved_set.has(person.name))}"
			data-person="${e(person.name)}" tabindex="0" aria-label="${e(person.full_name)}">
			<div class="rolodex-card-inner">
				<div class="rolodex-face rolodex-front">
					${save_button("data-save", person.name, this.saved_set.has(person.name))}
					${who_html(person.full_name, person.photo, sub)}
					<div class="rolodex-lines">${lines.join("")}</div>
					<div class="rolodex-contact">${contact_html(person)}</div>
				</div>
				<div class="rolodex-face rolodex-back">${this.back_html(person)}</div>
			</div>
		</article>`;
	}

	back_html(person) {
		const e = frappe.utils.escape_html;
		const facts = [
			[__("Positions"), person.positions.map(e).join(", ")],
			[
				__("Groups"),
				person.groups.map((name) => e(this.group_titles[name] || name)).join(", "),
			],
			[__("Birthday"), person.birthday && with_age(person)],
			[
				__("Anniversary"),
				person.anniversary && frappe.datetime.str_to_user(person.anniversary),
			],
			[__("Membership"), e(person.membership_status || "")],
			[__("Address"), e(person.address || "")],
		].filter(([, value]) => value);
		const body = facts.length
			? `<dl class="rolodex-facts">${facts
					.map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`)
					.join("")}</dl>`
			: `<p class="rolodex-muted">${__("Nothing more on file.")}</p>`;
		return `<div class="rolodex-back-head">
			<span class="rolodex-name">${e(person.full_name)}</span>${open_link("Person", person.name)}
		</div>
		<div class="rolodex-back-body">${body}</div>`;
	}

	household_html({ family, members, matched }) {
		const e = frappe.utils.escape_html;
		const all_saved = members.every((person) => this.saved_set.has(person.name));
		const head = members.find((person) => person.is_head_of_household) || members[0];
		const contact = family.phone || family.email || family.address ? family : head;
		const rows = members.map((person) => this.member_html(person, matched.has(person.name)));
		const details = members.map((person) => {
			const facts = [
				person.membership_status,
				person.phone,
				person.email,
				...person.positions,
			];
			const spans = facts.filter(Boolean).map((fact) => `<span>${e(fact)}</span>`);
			return `<li><strong>${e(person.full_name)}</strong>${spans.join(" · ")}</li>`;
		});
		return `<article class="${this.card_classes(family.name, all_saved)} rolodex-household"
			data-family="${e(family.name)}" tabindex="0" aria-label="${e(family.family_name)}">
			<div class="rolodex-card-inner">
				<div class="rolodex-face rolodex-front">
					${save_button("data-save-family", family.name, all_saved)}
					${who_html(family.family_name, family.photo, count_people(members.length))}
					<ul class="rolodex-members">${rows.join("")}</ul>
					<div class="rolodex-contact">${contact_html(contact)}</div>
				</div>
				<div class="rolodex-face rolodex-back">
					<div class="rolodex-back-head">
						<span class="rolodex-name">${e(family.family_name)}</span>${open_link("Family", family.name)}
					</div>
					<div class="rolodex-back-body"><ul class="rolodex-member-facts">${details.join("")}</ul></div>
				</div>
			</div>
		</article>`;
	}

	member_html(person, matched) {
		const e = frappe.utils.escape_html;
		const saved = this.saved_set.has(person.name);
		const head = person.is_head_of_household
			? `<span class="rolodex-head" title="${__("Head of household")}">★</span>`
			: "";
		return `<li class="${matched ? "" : "is-muted"}${
			saved ? " is-saved" : ""
		}" data-person="${e(person.name)}">
			${frappe.get_avatar("avatar-small", person.full_name, person.photo)}
			<span class="rolodex-member-name">${e(person.full_name)}${head}</span>
			${save_button("data-save", person.name, saved, "rolodex-save-small")}
		</li>`;
	}

	card_classes(name, saved) {
		return ["rolodex-card", this.flipped.has(name) && "is-flipped", saved && "is-saved"]
			.filter(Boolean)
			.join(" ");
	}

	empty_html() {
		const filtered = this.query || Object.values(this.filters).some((values) => values.size);
		const clear = filtered
			? `<button type="button" class="btn btn-default btn-sm" data-action="clear-all">${__(
					"Clear search and filters"
			  )}</button>`
			: "";
		return `<div class="rolodex-empty"><p>${
			filtered ? __("No one matches.") : __("No people yet.")
		}</p>${clear}</div>`;
	}

	render_rail(present) {
		const letters = LETTERS.map(
			(letter) =>
				`<button type="button" data-letter="${letter}"${
					present.has(letter) ? "" : " disabled"
				}>${letter}</button>`
		);
		this.$rail.html(`${letters.join("")}<span class="rolodex-rail-bubble" hidden></span>`);
	}

	render_facets() {
		const counts = this.count_values();
		const status = [
			...this.choices.status.map((name) => [name, name]),
			[NO_STATUS, __("No status")],
		];
		const facets = [
			["church", __("Church"), this.choices.church],
			["status", __("Membership"), status],
			["group", __("Group"), this.choices.group],
			["position", __("Position"), this.choices.position.map((name) => [name, name])],
		].filter(([facet, , options]) => options.length > (facet === "church" ? 1 : 0));
		this.labels = Object.fromEntries(
			facets.map(([facet, , options]) => [facet, Object.fromEntries(options)])
		);
		this.$facets.html(
			facets
				.map(([facet, label, options]) => this.facet_html(facet, label, options, counts))
				.join("")
		);
	}

	facet_html(facet, label, options, counts) {
		const e = frappe.utils.escape_html;
		const find =
			options.length > 8
				? `<input type="search" class="form-control input-xs rolodex-facet-find" placeholder="${__(
						"Find…"
				  )}">`
				: "";
		const rows = options.map(([value, text]) => {
			const checked = this.filters[facet].has(value) ? " checked" : "";
			return `<label class="rolodex-option"><input type="checkbox" value="${e(
				value
			)}"${checked}>
				<span>${e(text)}</span><small>${counts[facet][value] || 0}</small></label>`;
		});
		return `<section class="rolodex-facet" data-facet="${facet}">
			<h3>${label}</h3>${find}<div class="rolodex-options">${rows.join("")}</div>
		</section>`;
	}

	count_values() {
		const counts = { church: {}, status: {}, group: {}, position: {} };
		const add = (facet, value) => (counts[facet][value] = (counts[facet][value] || 0) + 1);
		for (const person of this.people) {
			add("church", person.church);
			add("status", person.membership_status || NO_STATUS);
			person.groups.forEach((name) => add("group", name));
			person.positions.forEach((name) => add("position", name));
		}
		return counts;
	}

	render_chips() {
		const e = frappe.utils.escape_html;
		const chips = Object.entries(this.filters).flatMap(([facet, values]) =>
			[...values].map(
				(
					value
				) => `<button type="button" class="rolodex-chip" data-facet="${facet}" data-value="${e(
					value
				)}"
					aria-label="${__("Remove filter {0}", [e(this.labels[facet][value])])}">${e(
					this.labels[facet][value]
				)}${icon("x")}</button>`
			)
		);
		const clear = `<button type="button" class="btn btn-link btn-xs" data-action="clear-filters">${__(
			"Clear all"
		)}</button>`;
		this.$chips.html(chips.length ? chips.join("") + clear : "");
		this.$root.find(".rolodex-filter-count").text(chips.length || "");
	}

	render_count(units) {
		const people = this.shown.length;
		const cards = units.length === 1 ? __("1 card") : __("{0} cards", [units.length]);
		const text =
			this.view === "households"
				? `${cards} · ${count_people(people)}`
				: count_people(people);
		this.$root.find(".rolodex-count").text(text);
		this.$root.find(".rolodex-sheet-done").text(__("Show {0}", [count_people(people)]));
		this.$root.find(".rolodex-shown-actions button").prop("disabled", !people);
	}

	render_tray() {
		const e = frappe.utils.escape_html;
		const people = this.saved.map((name) => this.by_name[name]);
		this.$tray.prop("hidden", !people.length);
		if (!people.length) {
			this.toggle_tray(false);
			return;
		}
		const stack = people
			.slice(-4)
			.map((person) => frappe.get_avatar("avatar-small", person.full_name, person.photo));
		this.$tray.find(".rolodex-stack").html(stack.join(""));
		this.$tray.find(".rolodex-tray-count").text(__("{0} saved", [people.length]));
		const items = people.map(
			(person) => `<li>
				<button type="button" data-jump="${e(person.name)}">
					${frappe.get_avatar("avatar-xs", person.full_name, person.photo)}<span>${e(
				person.full_name
			)}</span>
				</button>
				<button type="button" class="rolodex-unsave" data-unsave="${e(person.name)}" aria-label="${__(
				"Remove {0}",
				[e(person.full_name)]
			)}">${icon("x")}</button>
			</li>`
		);
		this.$tray.find(".rolodex-tray-list").html(items.join(""));
	}

	toggle_tray(open = !this.$tray.hasClass("is-open")) {
		this.$tray.toggleClass("is-open", open);
		this.$tray.find(".rolodex-tray-toggle").attr("aria-expanded", open);
	}

	run_action(action) {
		const shown = this.shown.map((person) => person.name);
		const actions = {
			"toggle-filters": () => this.toggle_filters(),
			"clear-filters": () => this.clear_filters(),
			"clear-all": () => this.clear_filters(true),
			"save-shown": () => this.save_all(shown),
			"email-shown": () => this.email(shown),
			"print-shown": () =>
				this.print(shown, __("People Directory"), this.view === "households"),
			"email-saved": () => this.email(this.saved),
			"print-saved": () => this.print(this.saved, __("Saved People"), false),
			"add-to-group": () => this.add_to_group(this.saved),
			"clear-saved": () =>
				frappe.confirm(__("Remove every saved card?"), () => this.update_saved([])),
		};
		actions[action]?.();
	}

	set_view(view) {
		this.view = view;
		this.mark_view();
		this.render();
		this.save_settings();
	}

	// Plain loops rather than jQuery's each(), which stops at the first callback returning
	// false, and classList.toggle() returns false whenever it turns a class off.
	mark_view() {
		for (const button of this.$root.find("[data-view]")) {
			button.classList.toggle("active", button.dataset.view === this.view);
			button.setAttribute("aria-pressed", button.dataset.view === this.view);
		}
	}

	set_filter(facet, value, on) {
		this.filters[facet][on ? "add" : "delete"](value);
		for (const input of this.$facets.find(`[data-facet="${facet}"] input`)) {
			if (input.value === value) input.checked = on;
		}
		this.render();
	}

	clear_filters(with_search = false) {
		Object.values(this.filters).forEach((values) => values.clear());
		this.$facets.find("input[type=checkbox]").prop("checked", false);
		if (with_search) {
			this.$search.val("");
			this.query = "";
		}
		this.render();
	}

	toggle_filters(open = !this.$root.hasClass("filters-open"), remember = true) {
		this.$root.toggleClass("filters-open", open);
		this.$root.find(".rolodex-filter-toggle").attr("aria-expanded", open);
		// Only the desktop panel is remembered; a phone always opens with the sheet down.
		if (remember && window.matchMedia(DESKTOP).matches) {
			this.filters_open = open;
			this.save_settings();
		}
	}

	is_sheet_open() {
		return this.$root.hasClass("filters-open") && !window.matchMedia(DESKTOP).matches;
	}

	flip(card) {
		const name = card.dataset.person || card.dataset.family;
		const flipped = !this.flipped.has(name);
		this.flipped[flipped ? "add" : "delete"](name);
		card.classList.toggle("is-flipped", flipped);
	}

	set_saved(names) {
		this.saved = names;
		this.saved_set = new Set(names);
	}

	update_saved(names) {
		this.set_saved(names);
		for (const el of this.$cards.find("[data-person]")) {
			el.classList.toggle("is-saved", this.saved_set.has(el.dataset.person));
		}
		for (const el of this.$cards.find("[data-save]")) {
			el.setAttribute("aria-pressed", this.saved_set.has(el.dataset.save));
		}
		for (const el of this.$cards.find("[data-save-family]")) {
			const members = this.members_of[el.dataset.saveFamily];
			const all = members.every((person) => this.saved_set.has(person.name));
			el.setAttribute("aria-pressed", all);
			el.closest(".rolodex-card").classList.toggle("is-saved", all);
		}
		this.render_tray();
		this.save_settings();
	}

	// Several names at once is a household: save them all unless all are saved already.
	toggle_saved(names) {
		const adding = names.some((name) => !this.saved_set.has(name));
		const kept = this.saved.filter((name) => adding || !names.includes(name));
		const added = adding ? names.filter((name) => !this.saved_set.has(name)) : [];
		this.update_saved([...kept, ...added]);
	}

	save_all(names) {
		const added = names.filter((name) => !this.saved_set.has(name));
		this.update_saved([...this.saved, ...added]);
		const message =
			added.length === 1 ? __("1 card saved.") : __("{0} cards saved.", [added.length]);
		frappe.show_alert({ message, indicator: "green" });
	}

	jump_to_letter(letter, scrubbing) {
		const section = this.$cards.find(`[data-letter="${letter}"]`)[0];
		if (!section) return;
		section.scrollIntoView({
			block: "start",
			behavior: scrubbing || reduced_motion() ? "auto" : "smooth",
		});
		this.$rail.find(".rolodex-rail-bubble").text(letter).prop("hidden", !scrubbing);
	}

	jump_to_card(name) {
		const card = this.$cards.find(`[data-person="${CSS.escape(name)}"]`)[0];
		if (!card) {
			frappe.show_alert({
				message: __("That card is hidden by the search or filters."),
				indicator: "orange",
			});
			return;
		}
		card.scrollIntoView({ block: "center", behavior: reduced_motion() ? "auto" : "smooth" });
		card.classList.add("is-flash");
		setTimeout(() => card.classList.remove("is-flash"), 1400);
	}

	email(names) {
		const e = frappe.utils.escape_html;
		const people = names.map((name) => this.by_name[name]).filter(Boolean);
		const emails = [...new Set(people.map((person) => person.email).filter(Boolean))];
		if (!emails.length)
			return frappe.msgprint(__("None of these people have an email address on file."));
		const mailto = `mailto:?bcc=${emails.map(encodeURIComponent).join(",")}`;
		const missing = people
			.filter((person) => !person.email)
			.map((person) => e(person.full_name));
		const notes = [
			emails.length === 1
				? __("The address goes in BCC.")
				: __("{0} addresses go in BCC, so no one sees the others.", [emails.length]),
		];
		if (missing.length) notes.push(__("No email on file for {0}.", [missing.join(", ")]));
		if (mailto.length > MAILTO_LIMIT)
			notes.push(
				__(
					"That is a long list, and some email apps cut it short. Copy the addresses instead."
				)
			);
		const dialog = new frappe.ui.Dialog({
			title: __("Email {0}", [count_people(people.length)]),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "notes",
					options: notes.map((note) => `<p>${note}</p>`).join(""),
				},
			],
			primary_action_label: __("Open Email"),
			primary_action: () => {
				window.location.href = mailto;
				dialog.hide();
			},
			secondary_action_label: __("Copy Addresses"),
			secondary_action: () =>
				frappe.utils.copy_to_clipboard(emails.join(", "), __("Addresses copied")),
		});
		dialog.show();
	}

	print(names, title, as_households) {
		const people = names.map((name) => this.by_name[name]).filter(Boolean);
		const cards = as_households ? this.household_print_cards(people) : people.map(print_card);
		const date = frappe.datetime.str_to_user(frappe.datetime.get_today());
		const $sheet = $(`<div class="rolodex-print">
			<header><h1>${frappe.utils.escape_html(title)}</h1><p>${date} · ${count_people(
			people.length
		)}</p></header>
			<div class="rolodex-print-grid">${cards.join("")}</div>
		</div>`).appendTo(document.body);
		document.body.classList.add("rolodex-printing");
		window.addEventListener(
			"afterprint",
			() => {
				$sheet.remove();
				document.body.classList.remove("rolodex-printing");
			},
			{ once: true }
		);
		const photos = $sheet
			.find("img")
			.toArray()
			.map((img) => img.decode().catch(() => null));
		Promise.all(photos).then(() => window.print());
	}

	household_print_cards(people) {
		const printed = new Set();
		return people.flatMap((person) => {
			const family = this.families[person.family];
			if (!family) return [print_card(person)];
			if (printed.has(family.name)) return [];
			printed.add(family.name);
			return [print_household(family, this.members_of[family.name])];
		});
	}

	add_to_group(names) {
		const dialog = new frappe.ui.Dialog({
			title: __("Add {0} to a group", [count_people(names.length)]),
			fields: [
				{
					fieldtype: "Link",
					fieldname: "group",
					label: __("Group"),
					options: "Group",
					reqd: 1,
				},
				{
					fieldtype: "Link",
					fieldname: "group_role",
					label: __("Role"),
					options: "Group Role",
				},
			],
			primary_action_label: __("Add"),
			primary_action: ({ group, group_role }) => {
				frappe
					.xcall(ADD_TO_GROUP_API, { group, group_role, people: names })
					.then((result) => {
						dialog.hide();
						for (const name of names) {
							const groups = this.by_name[name]?.groups;
							if (groups && !groups.includes(group)) groups.push(group);
						}
						this.render_facets();
						this.render();
						const title = this.group_titles[group] || group;
						let message = __("Added {0} to {1}.", [
							result.added,
							frappe.utils.escape_html(title),
						]);
						if (result.already_members === 1)
							message += " " + __("1 was already a member.");
						if (result.already_members > 1)
							message +=
								" " + __("{0} were already members.", [result.already_members]);
						frappe.show_alert({ message, indicator: "green" });
					});
			},
		});
		frappe.db
			.get_value("Group Role", { role: "Member" }, "name")
			.then((r) => dialog.set_value("group_role", r.message?.name));
		dialog.show();
	}

	// The toolbar sticks under the desk's own header; the letter tabs and rail stick under the toolbar.
	measure() {
		if (!this.$root) return;
		const navbar = document.querySelector(".navbar")?.offsetHeight || 0;
		const head = this.page.wrapper.find(".page-head").outerHeight() || 0;
		const toolbar = this.$root.find(".rolodex-toolbar").outerHeight() || 0;
		this.$root[0].style.setProperty("--rolodex-top", `${navbar + head}px`);
		this.$root[0].style.setProperty("--rolodex-cards-top", `${navbar + head + toolbar}px`);
		this.measure_tray();
	}

	// The tray is fixed to the bottom of the screen, because the desk scrolls an inner
	// element whose bottom padding would hold a sticky tray short of the edge. Line it up
	// with the cards, and leave room at the end of them so the last row can scroll clear.
	measure_tray() {
		const root = this.$root[0];
		const style = getComputedStyle(root);
		const box = root.getBoundingClientRect();
		const left = box.left + parseFloat(style.paddingLeft);
		const width = box.width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
		root.style.setProperty("--rolodex-tray-left", `${left}px`);
		root.style.setProperty("--rolodex-tray-width", `${width}px`);
		root.style.setProperty("--rolodex-tray-height", `${this.$tray[0].offsetHeight}px`);
	}
}

function rolodex_html() {
	return `<div class="rolodex">
		<div class="rolodex-toolbar">
			<div class="rolodex-toolbar-row">
				<label class="rolodex-search">${icon("search")}
					<input type="search" class="form-control" autocomplete="off" aria-label="${__("Search people")}"
						placeholder="${__("Search name, family, phone or email")}">
				</label>
				<div class="rolodex-view" role="group" aria-label="${__("View")}">
					<button type="button" data-view="people" class="active" aria-pressed="true">${__(
						"People"
					)}</button>
					<button type="button" data-view="households" aria-pressed="false">${__("Households")}</button>
				</div>
				<button type="button" class="btn btn-default btn-sm rolodex-btn rolodex-filter-toggle" data-action="toggle-filters"
					aria-expanded="false">${icon("filter")}<span>${__(
		"Filters"
	)}</span><span class="rolodex-filter-count"></span></button>
			</div>
			<div class="rolodex-chips"></div>
			<div class="rolodex-summary">
				<span class="rolodex-count" aria-live="polite"></span>
				<div class="rolodex-shown-actions">
					${action_button("save-shown", "bookmark", __("Save all"))}
					${action_button("email-shown", "email", __("Email all"))}
					${action_button("print-shown", "print", __("Print"))}
				</div>
			</div>
		</div>
		<div class="rolodex-body">
			<aside class="rolodex-filters" aria-label="${__("Filters")}">
				<div class="rolodex-sheet-head"><strong>${__("Filters")}</strong>
					<button type="button" class="btn btn-link btn-xs" data-action="clear-filters">${__(
						"Clear"
					)}</button>
				</div>
				<div class="rolodex-facets"></div>
				<div class="rolodex-sheet-foot">
					<button type="button" class="btn btn-primary btn-block rolodex-sheet-done" data-action="toggle-filters"></button>
				</div>
			</aside>
			<div class="rolodex-backdrop" data-action="toggle-filters"></div>
			<main class="rolodex-cards"></main>
			<nav class="rolodex-rail" aria-label="${__("Jump to letter")}"></nav>
		</div>
		<div class="rolodex-tray" hidden>
			<div class="rolodex-tray-bar">
				<button type="button" class="rolodex-tray-toggle" aria-expanded="false">
					<span class="rolodex-stack"></span><span class="rolodex-tray-count"></span>${icon("chevron")}
				</button>
				${action_button("email-saved", "email", __("Email"))}
				${action_button("print-saved", "print", __("Print"))}
				${action_button("add-to-group", "group", __("Add to Group"))}
				${action_button("clear-saved", "x", __("Clear"))}
			</div>
			<ul class="rolodex-tray-list"></ul>
		</div>
	</div>`;
}

function action_button(action, icon_name, label) {
	return `<button type="button" class="btn btn-default btn-sm rolodex-btn" data-action="${action}"
		title="${label}" aria-label="${label}">${icon(
		icon_name
	)}<span class="rolodex-label">${label}</span></button>`;
}

function save_button(attribute, name, saved, extra = "") {
	const label = saved ? __("Saved") : __("Save");
	return `<button type="button" class="rolodex-save ${extra}" ${attribute}="${frappe.utils.escape_html(
		name
	)}"
		aria-pressed="${saved}" title="${label}" aria-label="${label}">${icon("bookmark")}</button>`;
}

function who_html(title, photo, sub) {
	const e = frappe.utils.escape_html;
	return `<div class="rolodex-who">${frappe.get_avatar("avatar-large", title, photo)}
		<div class="rolodex-who-text"><div class="rolodex-name">${e(
			title
		)}</div><div class="rolodex-sub">${sub}</div></div>
	</div>`;
}

function contact_html(record) {
	const e = frappe.utils.escape_html;
	const tel = (record.phone || "").replace(/[^\d+]/g, "");
	const links = [
		tel && [`tel:${tel}`, "phone", __("Call")],
		tel && [`sms:${tel}`, "text", __("Text")],
		record.email && [`mailto:${record.email}`, "email", __("Email")],
		record.map_url && [record.map_url, "map", __("Map")],
	].filter(Boolean);
	return links
		.map(([href, name, label]) => {
			const target = name === "map" ? ' target="_blank" rel="noopener"' : "";
			return `<a class="rolodex-contact-btn" href="${e(
				href
			)}"${target} title="${label}" aria-label="${label}">${icon(name)}</a>`;
		})
		.join("");
}

function open_link(doctype, name) {
	const e = frappe.utils.escape_html;
	return `<a class="rolodex-open" href="${frappe.utils.get_form_link(
		doctype,
		name
	)}" data-doctype="${doctype}"
		data-name="${e(name)}">${icon("open")}<span>${__("Open")}</span></a>`;
}

function with_age(person) {
	const born = frappe.datetime.str_to_user(person.birthday);
	return person.age ? `${born} · ${__("age {0}", [person.age])}` : born;
}

function print_card(person) {
	const e = frappe.utils.escape_html;
	const lines = [
		person.family_title,
		person.membership_status,
		person.phone,
		person.email,
		person.address,
	];
	return `<article class="rolodex-print-card">${frappe.get_avatar(
		"avatar-medium",
		person.full_name,
		person.photo
	)}
		<div><strong>${e(person.full_name)}</strong>${lines
		.filter(Boolean)
		.map((line) => `<div>${e(line)}</div>`)
		.join("")}</div>
	</article>`;
}

function print_household(family, members) {
	const e = frappe.utils.escape_html;
	const lines = [family.phone, family.email, family.address].filter(Boolean);
	const rows = members.map((person) => {
		const contact = [person.phone, person.email].filter(Boolean).map(e).join(" · ");
		return `<li>${e(person.full_name)}${contact ? ` · ${contact}` : ""}</li>`;
	});
	return `<article class="rolodex-print-card">${frappe.get_avatar(
		"avatar-medium",
		family.family_name,
		family.photo
	)}
		<div><strong>${e(family.family_name)}</strong>${lines
		.map((line) => `<div>${e(line)}</div>`)
		.join("")}
		<ul>${rows.join("")}</ul></div>
	</article>`;
}

function count_people(count) {
	return count === 1 ? __("1 person") : __("{0} people", [count]);
}

function icon(name) {
	return `<svg class="rolodex-icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;
}

function sort_key(text) {
	return (text || "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
}

function compare(a, b) {
	return (a || "").localeCompare(b || "", undefined, { sensitivity: "base" });
}

function letter_of(key) {
	const letter = key.charAt(0).toUpperCase();
	return letter >= "A" && letter <= "Z" ? letter : "#";
}

function by_letter(units) {
	const sections = new Map(LETTERS.map((letter) => [letter, []]));
	for (const unit of units) sections.get(letter_of(unit.key)).push(unit);
	return [...sections].filter(([, items]) => items.length);
}

function reduced_motion() {
	return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
