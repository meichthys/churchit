// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.pages["check-in"].on_page_load = function (wrapper) {
	wrapper.station = new CheckInStation(wrapper);
};

frappe.pages["check-in"].on_page_show = function (wrapper) {
	wrapper.station.apply_route_options();
	wrapper.station.focus_search();
};

const API = "churchit.church_ministries.page.check_in.check_in";
const LAST_FUNCTION_KEY = "check_in_station_function";

const STATION_HTML = `
<style>
	.check-in-station { display: grid; grid-template-columns: minmax(0, 3fr) minmax(260px, 2fr); gap: var(--padding-xl); padding: var(--padding-md) var(--padding-lg) var(--padding-2xl); }
	@media (max-width: 900px) { .check-in-station { grid-template-columns: 1fr; } }
	.check-in-station .station-search { font-size: var(--text-xl); padding: 14px 16px; height: auto; }
	.check-in-station .station-hint { color: var(--text-muted); margin-top: var(--margin-sm); }
	.check-in-station .family-card { border: 1px solid var(--border-color); border-radius: var(--border-radius-md); padding: var(--padding-sm) var(--padding-md); margin-top: var(--margin-md); background: var(--card-bg); }
	.check-in-station .family-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; margin-bottom: var(--margin-xs); }
	.check-in-station .family-head .btn-link { padding: 0; }
	.check-in-station .members { display: flex; flex-wrap: wrap; gap: var(--margin-sm); }
	.check-in-station .member { display: flex; align-items: center; gap: 10px; border: 1px solid var(--border-color); border-radius: var(--border-radius-md); padding: 8px 14px 8px 8px; background: var(--bg-color); cursor: pointer; font-size: var(--text-lg); line-height: 1.2; text-align: left; }
	.check-in-station .member .avatar { flex: none; }
	.check-in-station .member small { display: block; color: var(--text-muted); font-size: var(--text-sm); }
	.check-in-station .member.selected { background: var(--primary); color: var(--white); border-color: var(--primary); }
	.check-in-station .member.selected small { color: inherit; opacity: 0.85; }
	.check-in-station .member.checked-in { opacity: 0.55; cursor: default; }
	.check-in-station .station-actions { position: sticky; bottom: 0; padding: var(--padding-md) 0; background: var(--bg-color); }
	.check-in-station .station-actions .btn { font-size: var(--text-lg); padding: 10px 24px; }
	.check-in-station .roster-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: var(--margin-sm); }
	.check-in-station .roster-row { display: flex; align-items: center; gap: var(--margin-sm); padding: 8px 0; border-bottom: 1px solid var(--border-color); }
	.check-in-station .roster-row .name { flex: 1; }
	.check-in-station .roster-row .time, .check-in-station .roster-row .code { color: var(--text-muted); font-size: var(--text-sm); }
	.check-in-station .roster-row .code { font-family: var(--font-family-mono, monospace); font-weight: 600; }
	.check-in-station .roster-row .btn { padding: 2px 6px; }
	.check-in-station .empty { color: var(--text-muted); padding: var(--padding-lg) 0; text-align: center; }
	.check-in-station .empty .add-visitor { color: var(--text-color); text-decoration: underline; cursor: pointer; }
</style>
<div class="check-in-station">
	<div>
		<input class="form-control station-search" type="search" autocomplete="off"
			placeholder="${__("Search by name or phone number…")}">
		<div class="station-hint">${__(
			"Tap the people who have arrived, then Check In. Press Enter to check in a single match."
		)}</div>
		<div class="station-results"></div>
		<div class="station-actions">
			<button class="btn btn-primary btn-check-in" disabled>${__("Check In")}</button>
			<button class="btn btn-default btn-clear">${__("Clear")}</button>
		</div>
	</div>
	<div class="station-roster">
		<div class="roster-head">
			<h5 class="m-0">${__("Checked In")} <span class="badge roster-count">0</span></h5>
			<a class="roster-function text-muted"></a>
		</div>
		<div class="roster-list"></div>
	</div>
</div>`;

class CheckInStation {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Check-In Station"),
			single_column: true,
		});
		this.selected = new Set();
		this.checked_in = new Set(); // persons already on the roster
		this.groups = [];
		this.make();
		this.load_context();
	}

	make() {
		this.function_field = this.make_function_field();
		this.print_field = this.page.add_field({
			fieldtype: "Check",
			fieldname: "print_tags",
			label: __("Print name tags"),
		});
		this.print_field.set_value(1);
		this.page.set_primary_action(
			__("New Visitor"),
			() => this.new_visitor(this.$search.val().trim()),
			"add"
		);
		this.page.add_menu_item(__("Check-In Settings"), () =>
			frappe.set_route("Form", "Check-In Settings")
		);
		this.page.add_menu_item(__("Function Check-Ins"), () =>
			frappe.set_route("List", "Function Check-In", { function: this.function })
		);

		this.$body = $(STATION_HTML).appendTo(this.page.body);
		this.$search = this.$body.find(".station-search");
		this.$results = this.$body.find(".station-results");
		this.$check_in = this.$body.find(".btn-check-in");
		this.$roster = this.$body.find(".roster-list");
		this.bind();
	}

	// Built directly because page.add_field() strips the arrow that opens the linked Function.
	make_function_field() {
		this.page.show_form();
		const field = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "function",
				label: __("Function"),
				placeholder: __("Function"),
				options: "Function",
				input_class: "input-xs",
				change: () => this.set_function(field.get_value()),
			},
			parent: this.page.page_form,
			only_input: true,
			with_link_btn: true,
			render_input: true,
		});
		$(field.wrapper).addClass("col-md-2").css("min-width", "280px");
		return field;
	}

	bind() {
		let timer;
		this.$search.on("input", () => {
			clearTimeout(timer);
			timer = setTimeout(() => this.search(), 200);
		});
		this.$search.on("keydown", (event) => {
			if (event.key === "Enter") this.check_in_from_enter();
			if (event.key === "Escape") this.clear();
		});
		this.$results.on("click", ".member:not(.checked-in)", (event) => {
			this.toggle($(event.currentTarget).data("person"));
		});
		this.$results.on("click", ".select-family", (event) => {
			$(event.currentTarget)
				.closest(".family-card")
				.find(".member:not(.checked-in)")
				.each((_, element) => this.selected.add($(element).data("person")));
			this.render_results();
		});
		this.$check_in.on("click", () => this.check_in([...this.selected]));
		this.$body.find(".btn-clear").on("click", () => this.clear());
		this.$results.on("click", ".add-visitor", () =>
			this.new_visitor(this.$search.val().trim())
		);
		this.$roster.on("click", ".btn-reprint", (event) => {
			church.name_tags.print_for({ check_ins: [$(event.currentTarget).data("name")] });
		});
		this.$roster.on("click", ".btn-undo", (event) =>
			this.undo($(event.currentTarget).data("name"))
		);
	}

	load_context() {
		frappe.call({ method: `${API}.get_station_context` }).then((r) => {
			this.context = r.message;
			this.apply_route_options();
		});
	}

	// A function named in the route wins; otherwise the first visit picks a default.
	apply_route_options() {
		if (!this.context) return;
		const wanted = frappe.route_options && frappe.route_options.function;
		frappe.route_options = null;
		const choice = wanted || (!this.function && this.default_function());
		if (choice && choice !== this.function) this.function_field.set_value(choice);
	}

	// The function last used on this computer, else the next one on the calendar.
	default_function() {
		const remembered = localStorage.getItem(LAST_FUNCTION_KEY);
		if (this.context.functions.some((f) => f.name === remembered)) return remembered;
		const next =
			this.context.functions.find((f) => f.start_date >= this.context.today) ||
			this.context.functions[0];
		return next && next.name;
	}

	set_function(name) {
		this.function = name;
		if (!name) return;
		localStorage.setItem(LAST_FUNCTION_KEY, name);
		frappe.db.get_value("Function", name, ["function_name", "start_date"]).then((r) => {
			const doc = r.message || {};
			this.$body
				.find(".roster-function")
				.attr("href", frappe.utils.get_form_link("Function", name))
				.text(
					[
						doc.function_name,
						doc.start_date && frappe.datetime.str_to_user(doc.start_date),
					]
						.filter(Boolean)
						.join(" · ")
				);
		});
		this.clear();
		this.refresh_roster();
	}

	focus_search() {
		this.$search.trigger("focus");
	}

	search() {
		const query = this.$search.val().trim();
		if (query.length < 2) {
			this.groups = [];
			this.render_results();
			return;
		}
		frappe.call({ method: `${API}.search_people`, args: { query } }).then((r) => {
			if (this.$search.val().trim() !== query) return;
			this.groups = r.message || [];
			this.render_results();
		});
	}

	render_results() {
		if (!this.groups.length) {
			const query = this.$search.val().trim();
			this.$results.html(
				query.length >= 2
					? `<div class="empty">${__("No one found.")} <a class="add-visitor">${__(
							"Add them as a new visitor."
					  )}</a></div>`
					: ""
			);
			this.update_button();
			return;
		}
		this.$results.html(this.groups.map((group) => this.family_card(group)).join(""));
		this.update_button();
	}

	family_card(group) {
		const title = frappe.utils.escape_html(group.family_name || "");
		const members = group.members.map((member) => this.member_chip(member)).join("");
		const select_all =
			group.members.length > 1
				? `<button class="btn btn-link btn-sm select-family">${__("Select all")}</button>`
				: "";
		return `<div class="family-card">
			<div class="family-head"><span>${title}</span>${select_all}</div>
			<div class="members">${members}</div>
		</div>`;
	}

	member_chip(member) {
		const checked_in = this.checked_in.has(member.name);
		const classes = ["member"];
		if (checked_in) classes.push("checked-in");
		else if (this.selected.has(member.name)) classes.push("selected");
		const detail = checked_in
			? __("Checked in")
			: member.age
			? __("Age {0}", [member.age])
			: "";
		return `<button type="button" class="${classes.join(" ")}" data-person="${member.name}">
			${frappe.get_avatar("avatar-medium", member.full_name, member.photo)}
			<span>
				${frappe.utils.escape_html(member.full_name)}${checked_in ? " ✓" : ""}
				<small>${detail}</small>
			</span>
		</button>`;
	}

	toggle(person) {
		if (this.selected.has(person)) this.selected.delete(person);
		else this.selected.add(person);
		this.render_results();
	}

	update_button() {
		const count = this.selected.size;
		this.$check_in
			.prop("disabled", !count || !this.function)
			.text(count ? __("Check In ({0})", [count]) : __("Check In"));
	}

	// Enter checks in the current selection, or the single matching person.
	check_in_from_enter() {
		if (this.selected.size) return this.check_in([...this.selected]);
		const matches = this.groups
			.flatMap((group) => group.members)
			.filter((member) => member.matched && !this.checked_in.has(member.name));
		if (matches.length === 1) this.check_in([matches[0].name]);
	}

	check_in(persons) {
		if (!persons.length || !this.function) return;
		return frappe
			.call({
				method: `${API}.check_in`,
				args: {
					function: this.function,
					persons,
					print_tags: this.print_field.get_value(),
				},
				freeze: true,
				freeze_message: __("Checking in…"),
			})
			.then((r) => {
				frappe.show_alert({
					message: __("{0} checked in.", [persons.length]),
					indicator: "green",
				});
				this.clear();
				this.refresh_roster();
				if (r.message.print) return church.name_tags.print(r.message.print);
			});
	}

	clear() {
		this.selected.clear();
		this.groups = [];
		this.$search.val("");
		this.render_results();
		this.focus_search();
	}

	refresh_roster() {
		if (!this.function) return;
		frappe
			.call({ method: `${API}.get_check_ins`, args: { function: this.function } })
			.then((r) => {
				const rows = r.message || [];
				this.checked_in = new Set(rows.map((row) => row.person));
				this.$body.find(".roster-count").text(rows.length);
				this.$roster.html(
					rows.length
						? rows.map((row) => this.roster_row(row)).join("")
						: `<div class="empty">${__("No one is checked in yet.")}</div>`
				);
				this.render_results();
			});
	}

	roster_row(row) {
		return `<div class="roster-row">
			<span class="name">${frappe.utils.escape_html(row.full_name)}</span>
			${row.security_code ? `<span class="code">${row.security_code}</span>` : ""}
			<span class="time">${frappe.datetime.comment_when(row.creation, true)}</span>
			<button class="btn btn-default btn-xs btn-reprint" data-name="${row.name}" title="${__(
			"Reprint name tag"
		)}">
				${frappe.utils.icon("printer", "sm")}
			</button>
			<button class="btn btn-default btn-xs btn-undo" data-name="${row.name}" title="${__(
			"Undo check-in"
		)}">
				${frappe.utils.icon("close", "sm")}
			</button>
		</div>`;
	}

	undo(name) {
		frappe.confirm(__("Remove this check-in?"), () => {
			frappe
				.call({ method: `${API}.undo_check_in`, args: { name } })
				.then(() => this.refresh_roster());
		});
	}

	// The search text seeds the dialog: words become the name, digits become the phone.
	new_visitor(query = "") {
		const is_phone = /^[\d\s()+.-]+$/.test(query);
		const [first_name, ...rest] = is_phone ? [] : query.split(/\s+/).filter(Boolean);
		const dialog = new frappe.ui.Dialog({
			title: __("New Visitor"),
			fields: [
				{
					fieldtype: "Data",
					fieldname: "first_name",
					label: __("First Name"),
					reqd: 1,
					default: first_name,
				},
				{
					fieldtype: "Data",
					fieldname: "last_name",
					label: __("Last Name"),
					default: rest.join(" "),
				},
				{ fieldtype: "Column Break" },
				{
					fieldtype: "Data",
					fieldname: "phone",
					label: __("Phone"),
					options: "Phone",
					default: is_phone ? query : "",
				},
				{
					fieldtype: "Link",
					fieldname: "family",
					label: __("Family"),
					options: "Family",
					description: __("Leave blank for a new visitor with no family record yet."),
				},
			],
			primary_action_label: __("Add & Check In"),
			primary_action: (values) => {
				frappe.call({ method: `${API}.add_visitor`, args: values }).then((r) => {
					dialog.hide();
					this.check_in([r.message.name]);
				});
			},
		});
		dialog.show();
	}
}
