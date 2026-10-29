// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Church Email", {
	setup(frm) {
		frm.set_query("smart_list", () => ({
			query: "churchit.church_people.smart_lists.search_smart_lists",
		}));
		frm.set_query("people", () => {
			const filters = { is_deceased: 0 };
			if (frappe.boot.churchit?.multi_church && frm.doc.church)
				filters.church = frm.doc.church;
			return { filters };
		});
	},

	refresh(frm) {
		if (frm.is_new()) return;

		const can_send = frappe.model.can_write("Church Email");
		if (["Draft", "Scheduled"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Preview"), () => preview(frm));
		}
		if (frm.doc.status === "Draft" && can_send) {
			const test_label = is_text(frm) ? __("Send Test Text") : __("Send Test Email");
			frm.add_custom_button(test_label, () => send_test(frm));
			frm.add_custom_button(__("Send"), () => send(frm)).addClass("btn-primary");
		} else if (frm.doc.status === "Scheduled") {
			frm.set_intro(
				__("This message will be sent at {0}.", [
					frappe.datetime.str_to_user(frm.doc.send_after),
				]),
				"orange"
			);
			if (can_send) {
				frm.add_custom_button(__("Unschedule"), () =>
					frm.call("unschedule").then(() => frm.reload_doc())
				);
			}
		} else if (frm.doc.status === "Sending") {
			frm.set_intro(
				__("This message is being sent. Reload the page to see when it is done."),
				"blue"
			);
		} else if (frm.doc.status === "Sent") {
			frm.set_intro(
				__("This message has been sent, so it can no longer be changed."),
				"green"
			);
			frm.disable_form();
		}
	},

	channel(frm) {
		frm.refresh();
	},

	email_template(frm) {
		if (!frm.doc.email_template) return;
		frappe.db
			.get_value("Email Template", frm.doc.email_template, [
				"subject",
				"use_html",
				"response",
				"response_html",
			])
			.then(({ message: template }) => {
				frm.set_value("subject", template.subject);
				frm.set_value(
					"message",
					template.use_html ? template.response_html : template.response
				);
			});
	},
});

function is_text(frm) {
	return frm.doc.channel === "Text Message";
}

function saved(frm) {
	return frm.is_dirty() ? frm.save() : Promise.resolve();
}

function nobody_gets_it(frm) {
	return is_text(frm)
		? __(
				"No one gets this text. Check Send To and Purpose: texts go only to people who agreed to get them."
		  )
		: __("No one gets this email. Check Send To and Purpose.");
}

function count_people(count) {
	return count === 1 ? __("1 person") : __("{0} people", [count]);
}

function send_test(frm) {
	saved(frm)
		.then(() => frm.call("send_test"))
		.then(({ message: address }) =>
			frappe.show_alert({
				message: __("Test sent to {0}", [frappe.utils.escape_html(address)]),
				indicator: "green",
			})
		);
}

function send(frm) {
	saved(frm)
		.then(() => frm.call("get_recipient_count"))
		.then(({ message: count }) => {
			if (!count) {
				frappe.msgprint(nobody_gets_it(frm));
				return;
			}
			const later =
				frm.doc.send_after && frappe.datetime.str_to_obj(frm.doc.send_after) > new Date();
			const people = count_people(count);
			const at = frappe.datetime.str_to_user(frm.doc.send_after);
			let question = is_text(frm)
				? __("Send this text to {0} now?", [people])
				: __("Send this email to {0} now?", [people]);
			if (later) {
				question = is_text(frm)
					? __("Send this text to {0} at {1}?", [people, at])
					: __("Send this email to {0} at {1}?", [people, at]);
			}
			frappe.confirm(question, () => frm.call("send").then(() => frm.reload_doc()));
		});
}

function preview(frm) {
	let shown;
	const dialog = new frappe.ui.Dialog({
		title: __("Preview"),
		size: "large",
		// Focus would open the Person dropdown over the message.
		no_focus: true,
		fields: [
			{
				fieldtype: "Link",
				fieldname: "person",
				label: __("Person"),
				options: "Person",
				description: __("Starts with the first person it goes to."),
				change() {
					const person = dialog.get_value("person");
					if (person && person !== shown) show(person);
				},
			},
			{ fieldtype: "HTML", fieldname: "preview" },
		],
	});
	const show = (person) =>
		frm.call("get_preview", { person }).then(({ message: result }) => {
			shown = result.person;
			if (result.person && !dialog.get_value("person")) dialog.set_value("person", shown);
			render_preview(frm, dialog.fields_dict.preview.$wrapper, result);
		});
	saved(frm).then(() => {
		dialog.show();
		show();
	});
}

function render_preview(frm, $wrapper, result) {
	if (!result.person) {
		$wrapper.html(`<p class="text-muted">${nobody_gets_it(frm)}</p>`);
		return;
	}
	const escape = frappe.utils.escape_html;
	const line = (label, value) =>
		`<div class="mb-2"><span class="text-muted">${label}</span> ${escape(value || "")}</div>`;
	const gets =
		result.count === 1
			? __("1 person gets this.")
			: __("{0} people get this.", [result.count]);
	if (result.text !== undefined) {
		$wrapper.html(`
			${line(__("To"), result.to)}
			<div class="p-3 mb-3 border rounded" style="white-space: pre-wrap">${escape(result.text)}</div>
			<p class="text-muted">${gets} ${__("{0} characters.", [result.text.length])}</p>
		`);
		return;
	}
	$wrapper.html(`
		${line(__("To"), result.to)}
		${line(__("Subject"), result.subject)}
		<iframe sandbox class="mb-3 border rounded w-100"
			style="height: 45vh; background: white"></iframe>
		<p class="text-muted">${gets}</p>
	`);
	// A sandboxed frame runs no script the message might hold, and keeps its styles to itself.
	$wrapper.find("iframe").attr("srcdoc", result.message);
}
