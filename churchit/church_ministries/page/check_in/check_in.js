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
const ROSTER_REFRESH_SECONDS = 10;

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
	.check-in-station .search-row { display: flex; gap: var(--margin-sm); }
	.check-in-station .search-row .btn { flex: none; font-size: var(--text-lg); }
	.pickup-families .pickup-family { border: 1px solid var(--border-color); border-radius: var(--border-radius-md); padding: var(--padding-sm) var(--padding-md); margin-top: var(--margin-md); }
	.pickup-families .pickup-heading { color: var(--text-muted); font-size: var(--text-sm); margin-top: var(--margin-sm); }
	.pickup-families .pickup-people { display: flex; flex-wrap: wrap; gap: var(--margin-md); margin-top: var(--margin-xs); }
	.pickup-families .pickup-person { display: flex; align-items: center; gap: 10px; font-size: var(--text-lg); line-height: 1.2; }
	.pickup-families .pickup-person small { display: block; color: var(--text-muted); font-size: var(--text-sm); white-space: pre-line; }
	.pickup-families .pickup-child { display: flex; align-items: center; gap: 10px; margin: 0; }
	.pickup-families .empty { color: var(--text-muted); padding: var(--padding-lg) 0; text-align: center; font-size: var(--text-lg); }
</style>
<div class="check-in-station">
	<div>
		<div class="search-row">
			<input class="form-control station-search" type="search" autocomplete="off"
				placeholder="${__("Search by name or phone number…")}">
			<button class="btn btn-default btn-scan-card">
				${frappe.utils.icon("scan-barcode", "md")} ${__("Scan Card")}
			</button>
		</div>
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
			<div class="text-right">
				<a class="roster-function text-muted"></a>
				<div class="roster-rooms text-muted small"></div>
			</div>
		</div>
		<input class="form-control input-xs roster-filter mb-2" type="search" autocomplete="off"
			placeholder="${__("Filter by name or code")}">
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
		$(wrapper).on("show", () => this.start_polling());
		$(wrapper).on("hide", () => this.stop_polling());
		document.addEventListener("visibilitychange", () => this.start_polling());
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
		this.page.set_secondary_action(__("Verify Pickup"), () => this.verify_pickup());
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
		this.$roster_filter = this.$body.find(".roster-filter");
		this.bind();
		this.make_team_tab();
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
		this.$results.on("click", ".member-care", (event) => {
			event.stopPropagation();
			this.show_care($(event.currentTarget).data("person"));
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
		this.$body.find(".btn-scan-card").on("click", () => this.scan_card());
		this.$results.on("click", ".add-visitor", () =>
			this.new_visitor(this.$search.val().trim())
		);
		this.$roster.on("click", ".btn-reprint", (event) => {
			church.name_tags.print_for({ check_ins: [$(event.currentTarget).data("name")] });
		});
		this.$roster.on("click", ".btn-undo", (event) =>
			this.undo($(event.currentTarget).data("name"))
		);
		this.$roster.on("click", ".btn-page", (event) =>
			this.page_parents($(event.currentTarget).data("name"))
		);
		this.$roster.on("click", ".btn-check-out", (event) =>
			this.check_out($(event.currentTarget).data("name"))
		);
		this.$roster_filter.on("input", () => this.render_roster());
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
		if (!name) return this.stop_polling();
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
		this.start_polling();
		this.show_rooms();
		this.show_headcount();
		this.refresh_team();
	}

	// People counted in the room, named or not. The attendance total takes the larger count.
	show_headcount() {
		if (!this.$headcount) {
			this.$headcount = $(`<div class="headcount d-flex align-items-center mb-3">
				<label class="m-0 mr-2 text-muted">${__("Headcount")}</label>
				<input class="form-control input-xs mr-2" type="number" min="0" style="width: 6em">
				<button class="btn btn-default btn-xs">${__("Save")}</button>
			</div>`).insertAfter(this.$body.find(".roster-head"));
			const save = () =>
				frappe
					.call({
						method: "churchit.church_ministries.attendance.set_headcount",
						args: {
							function: this.function,
							headcount: this.$headcount.find("input").val() || 0,
						},
					})
					.then((r) =>
						frappe.show_alert({
							message: __("Attendance total: {0}", [r.message]),
							indicator: "green",
						})
					);
			this.$headcount.find("button").on("click", save);
			this.$headcount
				.find("input")
				.on("keydown", (event) => event.key === "Enter" && save());
		}
		const name = this.function;
		frappe.db.get_value("Function", name, ["start_date", "headcount"]).then((r) => {
			const doc = r.message || {};
			if (name !== this.function) return;
			// The server refuses a headcount before the function starts.
			this.$headcount.toggle(
				Boolean(doc.start_date) && doc.start_date <= frappe.datetime.get_today()
			);
			this.$headcount.find("input").val(doc.headcount || "");
		});
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
		frappe
			.call({
				method: `${API}.search_people`,
				args: { query, function: this.function },
			})
			.then((r) => {
				if (this.$search.val().trim() !== query) return;
				this.groups = r.message || [];
				this.render_results();
			});
	}

	// A member card's QR code holds the Person ID; the server applies the search's own rules to it.
	// A pre check-in code from the member portal starts with "f=".
	scan_card() {
		new frappe.ui.Scanner({
			dialog: true,
			multiple: false,
			on_scan: (data) => {
				const text = data.result.text;
				if (text.startsWith("f=")) this.check_in_code(text);
				else this.show_card_holder(text);
			},
		});
	}

	// The code names its own function, which may not be the one this station shows.
	check_in_code(payload) {
		frappe
			.call({
				method: "churchit.church_ministries.pre_check_in.check_in",
				args: { payload, print_tags: this.print_field.get_value() },
				freeze: true,
				freeze_message: __("Checking in…"),
			})
			.then((r) => {
				const result = r.message;
				const function_name = frappe.utils.escape_html(result.function_name);
				frappe.show_alert({
					message: result.new.length
						? __("{0} checked in to {1}.", [result.new.length, function_name])
						: __("Already checked in to {0}.", [function_name]),
					indicator: result.new.length ? "green" : "orange",
				});
				if (result.capacity_warning) {
					frappe.show_alert(
						{ message: result.capacity_warning, indicator: "orange" },
						10
					);
				}
				this.refresh_roster();
				if (result.print) return church.name_tags.print(result.print);
			});
	}

	show_card_holder(person) {
		frappe
			.call({
				method: `${API}.find_card_holder`,
				args: { person, function: this.function },
			})
			.then((r) => {
				this.$search.val("");
				this.groups = r.message || [];
				this.render_results();
				this.focus_search();
				if (!this.groups.length) {
					frappe.show_alert({
						message: __("No one found for this card."),
						indicator: "orange",
					});
				}
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
			: [member.age && __("Age {0}", [member.age]), member.grade]
					.filter(Boolean)
					.join(" · ");
		const allergies = member.alergies
			? `<span class="indicator-pill red mt-1">${__("Allergies: {0}", [
					frappe.utils.escape_html(member.alergies),
			  ])}</span>`
			: "";
		// The server sends these only to readers of Person permission level 1.
		const care =
			member.medical_notes || member.emergency_contact_name || member.emergency_contact_phone
				? `<span class="member-care" role="button" data-person="${member.name}"
					title="${__("Medical notes and emergency contact")}">
					${frappe.utils.icon("stethoscope", "md")}
				</span>`
				: "";
		return `<button type="button" class="${classes.join(" ")}" data-person="${member.name}">
			${frappe.get_avatar("avatar-medium", member.full_name, member.photo)}
			<span>
				${frappe.utils.escape_html(member.full_name)}${checked_in ? " ✓" : ""}
				<small>${frappe.utils.escape_html(detail)}</small>
				${allergies}
			</span>
			${care}
		</button>`;
	}

	show_care(person) {
		const member = this.groups
			.flatMap((group) => group.members)
			.find((row) => row.name === person);
		const contact = [member.emergency_contact_name, member.emergency_contact_phone]
			.filter(Boolean)
			.join(", ");
		const section = (label, text) =>
			text
				? `<p class="text-muted mb-1">${label}</p>
				<p style="white-space: pre-line">${frappe.utils.escape_html(text)}</p>`
				: "";
		frappe.msgprint({
			title: frappe.utils.escape_html(member.full_name),
			message:
				section(__("Allergies"), member.alergies) +
				section(__("Medical Notes"), member.medical_notes) +
				section(__("Emergency Contact"), contact),
		});
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

	// A person outside the function's age or grade limits is checked in only after a confirm.
	check_in(persons, kind) {
		if (!persons.length || !this.function) return;
		const send = () =>
			frappe
				.call({
					method: `${API}.check_in`,
					args: {
						function: this.function,
						persons,
						print_tags: this.print_field.get_value(),
						kind,
					},
					freeze: true,
					freeze_message: __("Checking in…"),
				})
				.then((r) => {
					frappe.show_alert({
						message: __("{0} checked in.", [persons.length]),
						indicator: "green",
					});
					if (r.message.capacity_warning) {
						frappe.show_alert(
							{ message: r.message.capacity_warning, indicator: "orange" },
							10
						);
					}
					this.clear();
					this.refresh_roster();
					if (r.message.print) return church.name_tags.print(r.message.print);
				});
		if (kind === "Volunteer") return send();
		return frappe
			.call({
				method: "churchit.church_ministries.check_in_limits.get_bound_problems",
				args: { function: this.function, persons },
			})
			.then((r) => {
				const problems = Object.values(r.message || {});
				if (!problems.length) return send();
				const escape = frappe.utils.escape_html;
				const lines = problems.map(
					({ full_name, problem }) =>
						`<li><b>${escape(full_name)}</b>: ${escape(problem)}</li>`
				);
				frappe.confirm(
					`<p>${__("Outside the age or grade limits of this function:")}</p>
					<ul>${lines.join("")}</ul>
					<p>${__("Check in anyway?")}</p>`,
					send
				);
			});
	}

	clear() {
		this.selected.clear();
		this.groups = [];
		this.$search.val("");
		this.render_results();
		this.focus_search();
	}

	// Loads the roster now and every 10 s while a function is picked and this page is in view, so other
	// stations' check-ins and checkouts show; a hidden tab or another page sends nothing.
	start_polling() {
		this.stop_polling();
		if (!this.function || document.hidden || frappe.get_route()[0] !== "check-in") return;
		this.poll_roster();
		this.poll = setInterval(() => this.poll_roster(), ROSTER_REFRESH_SECONDS * 1000);
	}

	stop_polling() {
		clearInterval(this.poll);
		clearTimeout(this.poll_retry);
	}

	// A poll is quiet. After a failed poll the station waits 1, 2, 4, then 8 minutes before it asks again,
	// so a station that lost the server does not add an error to the dialog every 10 s.
	poll_roster() {
		this.refresh_roster(true).then(
			() => (this.poll_failures = 0),
			() => {
				this.stop_polling();
				this.poll_failures = (this.poll_failures || 0) + 1;
				const minutes = Math.min(2 ** (this.poll_failures - 1), 8);
				this.poll_retry = setTimeout(() => this.start_polling(), minutes * 60 * 1000);
			}
		);
	}

	refresh_roster(silent = false) {
		const name = this.function;
		if (!name) return Promise.resolve();
		const args = { function: name };
		return frappe.call({ method: `${API}.get_check_ins`, args, silent }).then((r) => {
			const rows = r.message || [];
			// A poll that finds no change leaves the page alone, so a tap in progress is not lost.
			if (
				name !== this.function ||
				JSON.stringify(rows) === JSON.stringify(this.roster_rows)
			)
				return;
			this.roster_rows = rows;
			this.checked_in = new Set(rows.map((row) => row.person));
			this.$body.find(".roster-count").text(rows.length);
			this.render_roster();
			this.render_results();
		});
	}

	render_roster() {
		const rows = this.roster_rows || [];
		const query = this.$roster_filter.val().trim().toLowerCase();
		const shown = rows.filter((row) =>
			`${row.full_name} ${row.security_code || ""}`.toLowerCase().includes(query)
		);
		const empty = rows.length ? __("No one matches.") : __("No one is checked in yet.");
		this.$roster.html(
			shown.length
				? shown.map((row) => this.roster_row(row)).join("")
				: `<div class="empty">${empty}</div>`
		);
	}

	// A child with a pickup tag leaves through Verify Pickup; anyone else is checked out here.
	roster_row(row) {
		const button = (action, icon, title) =>
			`<button class="btn btn-default btn-xs ${action}"
				data-name="${row.name}" title="${title}">${frappe.utils.icon(icon, "sm")}</button>`;
		const is_in = !row.collected_at;
		const status = is_in
			? `<span class="indicator-pill green">${__("In")}</span>`
			: `<span class="indicator-pill gray">${
					row.collected_by_name
						? __("Collected by {0}", [frappe.utils.escape_html(row.collected_by_name)])
						: __("Checked out")
			  }</span>`;
		return `<div class="roster-row">
			${frappe.get_avatar("avatar-small", row.full_name, row.photo)}
			<span class="name">${frappe.utils.escape_html(row.full_name)}</span>
			${row.security_code ? `<span class="code">${row.security_code}</span>` : ""}
			${status}
			<span class="time">${frappe.datetime.comment_when(row.collected_at || row.creation, true)}</span>
			${is_in ? button("btn-page", "bell-ring", __("Page parents")) : ""}
			${is_in && !row.security_code ? button("btn-check-out", "log-out", __("Check out")) : ""}
			${button("btn-reprint", "printer", __("Reprint name tag"))}
			${is_in ? button("btn-undo", "close", __("Undo check-in")) : ""}
		</div>`;
	}

	check_out(check_in) {
		frappe.confirm(__("Check this person out?"), () => {
			frappe
				.call({
					method: "churchit.church_ministries.page.check_in.checkout.check_out",
					args: { check_in },
				})
				.then(() => this.refresh_roster());
		});
	}

	show_rooms() {
		const name = this.function;
		frappe
			.call({
				method: "churchit.church_ministries.check_in_limits.get_rooms",
				args: { function: name },
			})
			.then((r) => {
				if (name !== this.function) return;
				this.$body.find(".roster-rooms").text(r.message.join(", "));
			});
	}

	undo(name) {
		frappe.confirm(__("Remove this check-in?"), () => {
			frappe
				.call({ method: `${API}.undo_check_in`, args: { name } })
				.then(() => this.refresh_roster());
		});
	}

	// The server sends a fixed message to the child's household Adults and names who it reached.
	page_parents(check_in) {
		frappe.confirm(__("Ask this child's parents to come?"), () => {
			frappe
				.call({
					method: "churchit.church_ministries.page.check_in.paging.page_parents",
					args: { check_in },
					freeze: true,
				})
				.then((r) => {
					const reached = (r.message || []).map(frappe.utils.escape_html);
					if (reached.length) {
						frappe.show_alert({
							message: __("Paged {0}.", [reached.join(", ")]),
							indicator: "green",
						});
						return;
					}
					frappe.msgprint({
						title: __("No parent reached"),
						message: __("No parent could get a text or an email. Send a runner."),
						indicator: "orange",
					});
				});
		});
	}

	// The Team tab lists who serves at the Function. They check in as Volunteers: no code, no pickup tag.
	make_team_tab() {
		const $people = this.$body.find(
			".search-row, .station-hint, .station-results, .station-actions"
		);
		const $tabs = $(`<ul class="nav nav-tabs mb-3">
			<li class="nav-item">
				<a class="nav-link active" role="button" data-tab="people">${__("People")}</a>
			</li>
			<li class="nav-item">
				<a class="nav-link" role="button" data-tab="team">${__("Team")}</a>
			</li>
		</ul>`).insertBefore(this.$body.find(".search-row"));
		this.$team = $(`<div class="station-team"></div>`)
			.hide()
			.insertAfter(this.$body.find(".station-actions"));
		$tabs.on("click", ".nav-link", (event) => {
			const is_team = event.currentTarget.dataset.tab === "team";
			$tabs.find(".nav-link").removeClass("active");
			$(event.currentTarget).addClass("active");
			$people.toggle(!is_team);
			this.$team.toggle(is_team);
			if (is_team) this.refresh_team();
			else this.focus_search();
		});
		this.$team.on("click", ".btn-team-check-in", (event) => {
			const check_in = this.check_in([event.currentTarget.dataset.person], "Volunteer");
			if (check_in) check_in.then(() => this.refresh_team());
		});
	}

	refresh_team() {
		if (!this.function || !this.$team.is(":visible")) return;
		frappe
			.call({
				method: "churchit.church_ministries.page.check_in.team.get_team",
				args: { function: this.function },
			})
			.then((r) => {
				const team = r.message || [];
				this.$team.html(
					team.length
						? team.map((row) => this.team_row(row)).join("")
						: `<div class="empty">${__(
								"No one has accepted a Ministry Team position at this Function."
						  )}</div>`
				);
			});
	}

	team_row(row) {
		const action = row.is_checked_in
			? `<span class="text-muted">${__("Checked in")}</span>`
			: `<button class="btn btn-default btn-sm btn-team-check-in" data-person="${
					row.person
			  }">${__("Check In")}</button>`;
		return `<div class="roster-row">
			${frappe.get_avatar("avatar-medium", row.person_name)}
			<span class="name">
				${frappe.utils.escape_html(row.person_name)}
				<small class="d-block text-muted">${frappe.utils.escape_html(row.position || "")}</small>
			</span>
			${action}
		</div>`;
	}

	// The volunteer compares the person at the desk with who may collect, then records who took each child.
	verify_pickup() {
		const dialog = new frappe.ui.Dialog({
			title: __("Verify Pickup"),
			size: "large",
			fields: [
				{
					fieldtype: "Data",
					fieldname: "code",
					label: __("Security Code"),
					description: __("The 4 characters on the pickup tag."),
					reqd: 1,
				},
				{
					fieldtype: "Button",
					fieldname: "scan",
					label: __("Scan"),
					// The pickup tag's QR code holds the security code.
					click: () =>
						new frappe.ui.Scanner({
							dialog: true,
							multiple: false,
							on_scan: (data) => {
								dialog.set_value("code", data.result.text);
								this.show_pickup(dialog, data.result.text);
							},
						}),
				},
				{ fieldtype: "HTML", fieldname: "families" },
			],
			primary_action_label: __("Verify"),
			primary_action: ({ code }) => this.show_pickup(dialog, code),
		});
		// As Frappe's own Enter-to-submit does: blur first, so the typed code reaches the dialog's values.
		dialog.fields_dict.code.$input.on("keydown", (event) => {
			if (event.key === "Enter") frappe.app.trigger_primary_action();
		});
		dialog.show();
	}

	show_pickup(dialog, code) {
		return frappe.call({ method: `${API}.get_pickup_families`, args: { code } }).then((r) => {
			this.render_pickup(dialog, code, r.message || []);
			dialog.fields_dict.code.$input.trigger("select");
		});
	}

	render_pickup(dialog, code, families) {
		const $wrapper = dialog.fields_dict.families.$wrapper;
		$wrapper.html(
			`<div class="pickup-families">${
				families.length
					? families.map((family) => this.pickup_family(family)).join("")
					: `<div class="empty">${__(
							"No child is checked in with this code today."
					  )}</div>`
			}</div>`
		);
		$wrapper.find(".pickup-release").on("click", (event) => {
			const $family = $(event.currentTarget).closest(".pickup-family");
			const check_ins = $family
				.find(".pickup-child input:checked")
				.map((index, input) => input.value)
				.get();
			if (!check_ins.length) {
				frappe.msgprint(__("Tick the children this person is collecting."));
				return;
			}
			const collector = event.currentTarget.dataset.collector;
			const release = (override_reason) =>
				frappe
					.call({
						method: `${API}.release_children`,
						args: { code, check_ins, collector, override_reason },
						freeze: true,
					})
					.then((r) => this.render_pickup(dialog, code, r.message || []));
			const family = families.find((row) =>
				row.children.some((child) => check_ins.includes(child.check_in))
			);
			const ticked = family.children
				.filter((child) => check_ins.includes(child.check_in))
				.map((child) => child.person);
			const is_restricted = family.restrictions.some(
				(row) => row.restricted_person === collector && ticked.includes(row.child)
			);
			// The server refuses everyone else; only a Church Manager may override, with a reason.
			if (!is_restricted || !frappe.user.has_role("Church Manager")) {
				release();
				return;
			}
			frappe.prompt(
				{
					fieldtype: "Small Text",
					fieldname: "reason",
					label: __("Override Reason"),
					description: __(
						"A Pickup Restriction names this person. Say why you release the child to them."
					),
					reqd: 1,
				},
				({ reason }) => release(reason),
				__("Override Pickup Restriction"),
				__("Release")
			);
		});
	}

	pickup_family(family) {
		const children = family.children.map((child) => this.pickup_child(child));
		const release = family.children.some((child) => !child.collected_by);
		const names = Object.fromEntries(
			family.children.map((child) => [child.person, child.full_name])
		);
		const restricted_from = (person) =>
			family.restrictions
				.filter((row) => row.restricted_person === person)
				.map((row) => __("Restricted from collecting {0}", [names[row.child]]));
		const collector = (person, detail) =>
			this.pickup_person(
				person.full_name,
				person.photo,
				[detail, ...restricted_from(person.name)].join("\n"),
				release && person.name
			);
		const restrictions = family.restrictions.map((row) =>
			this.pickup_person(
				row.restricted_name,
				null,
				[
					__("May not collect {0}", [names[row.child]]),
					row.description,
					row.valid_until &&
						__("Until {0}", [frappe.datetime.str_to_user(row.valid_until)]),
				]
					.filter(Boolean)
					.join("\n")
			)
		);
		const collectors = [
			...family.adults.map((adult) => collector(adult, __("Adult of the household"))),
			...family.pickups.map((pickup) =>
				collector(
					pickup,
					[pickup.relationship || __("Authorized pickup"), pickup.notes]
						.filter(Boolean)
						.join("\n")
				)
			),
		];
		const title = family.family_name || __("No family on file");
		return `<div class="pickup-family">
			<h5 class="m-0">${frappe.utils.escape_html(title)}</h5>
			<div class="pickup-heading">${__("Checked in with this code today")}</div>
			<div class="pickup-people">${children.join("")}</div>
			<div class="pickup-heading">${__("May collect them")}</div>
			<div class="pickup-people">${
				collectors.join("") || __("No one is on file. Ask a member of staff.")
			}</div>
			${
				restrictions.length
					? `<div class="pickup-heading text-danger">${__("Pickup Restrictions")}</div>
						<div class="pickup-people">${restrictions.join("")}</div>`
					: ""
			}
		</div>`;
	}

	// A child not collected yet is ticked for release; a collected one says who took them and when.
	pickup_child(child) {
		if (child.collected_by) {
			return this.pickup_person(
				child.full_name,
				child.photo,
				__("Collected by {0} at {1}", [
					child.collected_by_name,
					frappe.datetime.str_to_user(child.collected_at),
				])
			);
		}
		return `<label class="pickup-child">
			<input type="checkbox" value="${frappe.utils.escape_html(child.check_in)}" checked>
			${this.pickup_person(child.full_name, child.photo, child.function_name)}
		</label>`;
	}

	pickup_person(name, photo, detail, collector) {
		const release = collector
			? `<button type="button" class="btn btn-sm btn-default pickup-release"
				data-collector="${frappe.utils.escape_html(collector)}">${__("Release")}</button>`
			: "";
		return `<div class="pickup-person">
			${frappe.get_avatar("avatar-xl", name, photo)}
			<span>
				${frappe.utils.escape_html(name)}
				<small>${frappe.utils.escape_html(detail || "")}</small>
			</span>
			${release}
		</div>`;
	}

	// The search text seeds the dialog: words become the name, digits become the phone.
	new_visitor(query = "") {
		const is_phone = /^[\d\s()+.-]+$/.test(query);
		const [first_name, ...rest] = is_phone ? [] : query.split(/\s+/).filter(Boolean);
		// People on file who may be the visitor are offered once, before anyone new is added.
		let matches_shown = false;
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
				{
					fieldtype: "Section Break",
					label: __("Emergency Contact"),
					collapsible: 1,
					description: __("For a visitor with no household adult in Churchit."),
				},
				{
					fieldtype: "Data",
					fieldname: "emergency_contact_name",
					label: __("Emergency Contact Name"),
				},
				{ fieldtype: "Column Break" },
				{
					fieldtype: "Data",
					fieldname: "emergency_contact_phone",
					label: __("Emergency Contact Phone"),
					options: "Phone",
				},
				{ fieldtype: "Section Break" },
				{ fieldtype: "HTML", fieldname: "matches" },
			],
			primary_action_label: __("Add & Check In"),
			primary_action: (values) => {
				if (matches_shown) return add(values);
				frappe
					.call({
						method: "churchit.church_ministries.page.check_in.visitors.find_visitor_matches",
						args: {
							function: this.function,
							first_name: values.first_name,
							last_name: values.last_name,
							phone: values.phone,
						},
					})
					.then((r) => {
						if (!(r.message || []).length) return add(values);
						matches_shown = true;
						this.show_visitor_matches(dialog, r.message);
					});
			},
		});
		const add = (values) =>
			frappe.call({ method: `${API}.add_visitor`, args: values }).then((r) => {
				dialog.hide();
				this.check_in([r.message.name], "Guest");
			});
		dialog.show();
	}

	show_visitor_matches(dialog, groups) {
		const matches = groups.flatMap((group) =>
			group.members
				.filter((member) => member.matched)
				.map((member) => ({ ...member, family_name: group.family_name }))
		);
		const rows = matches.map((member) => {
			const detail = [member.family_name, member.age && __("Age {0}", [member.age])]
				.filter(Boolean)
				.join(" · ");
			return `<div class="d-flex align-items-center mb-2">
				${frappe.get_avatar("avatar-medium", member.full_name, member.photo)}
				<span class="flex-fill ml-2">
					${frappe.utils.escape_html(member.full_name)}
					<small class="d-block text-muted">${frappe.utils.escape_html(detail)}</small>
				</span>
				<button type="button" class="btn btn-sm btn-primary visitor-match"
					data-person="${member.name}">${__("Check In")}</button>
			</div>`;
		});
		const $wrapper = dialog.fields_dict.matches.$wrapper;
		$wrapper.html(
			`<p class="text-muted">${__(
				"They may already be on file. Check in the right person, or add them as a new visitor."
			)}</p>${rows.join("")}`
		);
		$wrapper.find(".visitor-match").on("click", (event) => {
			dialog.hide();
			this.check_in([event.currentTarget.dataset.person], "Guest");
		});
		dialog.get_primary_btn().text(__("Add as New Visitor"));
	}
}
