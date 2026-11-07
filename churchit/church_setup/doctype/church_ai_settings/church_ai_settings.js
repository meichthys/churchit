// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

const escape = (text) => frappe.utils.escape_html(text || "");
const MANAGER_ROLES = ["System Manager", "Church Manager"];
const PILL_COLORS = { true: "orange", false: "green", null: "gray" };

frappe.ui.form.on("Church AI Settings", {
	refresh(frm) {
		frm.get_field("intro_html").$wrapper.html(intro_html());
		const warnings = get_warnings(Boolean(frappe.boot.churchit?.ai?.flow));
		for (const [fieldname, html] of Object.entries(warnings)) {
			frm.get_field(`${fieldname}_html`).$wrapper.html(
				`<div style="max-width: 46rem">${html}</div>`
			);
		}

		const is_manager = frappe.user.has_role(MANAGER_ROLES);
		frm.toggle_display(["exposure_section", "use_recommended_list"], is_manager);
		if (is_manager) show_exposure(frm);
	},

	use_recommended_list(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first, then use the recommended list."));
			return;
		}
		frappe
			.xcall("churchit.ai.flow_switch.use_recommended_knowledge_doctypes", {}, "POST", {
				freeze: true,
			})
			.then((added) => {
				frappe.show_alert({
					message: added
						? __("DocTypes added to the list: {0}.", [added])
						: __("The list already has every recommended DocType."),
					indicator: added ? "green" : "blue",
				});
				if (added) frm.reload_doc();
			});
	},
});

function intro_html() {
	const summary = [
		__(
			"A connected AI app can see and change everything that its user can see and change. A hosted AI app sends everything it reads to the company that runs it."
		),
		__("Read each warning below before you turn AI on."),
	].join(" ");
	return `<div style="max-width: 46rem">
		<div class="form-message yellow"><div>${escape(summary)}</div></div>
	</div>`;
}

function get_warnings(has_flow) {
	const only_with_flow = (texts) => (has_flow ? texts : []);
	return {
		warning_app: paragraphs([
			__(
				"An AI app works as the person who connected it. It can see and change everything that person can see and change in the desk. If the person can read care notes, counseling, medical notes, giving or the details of children, the AI app can read them too."
			),
			__(
				"An AI app can change records as fast as it can read them, many records in the time a person changes one."
			),
		]),
		warning_data: paragraphs([
			__(
				"A hosted AI app, such as Claude, ChatGPT or Gemini, sends everything it reads to the company that runs it. That company's terms then apply to your church's data."
			),
			__(
				"A local AI model on your own computer, for example in Ollama or LM Studio, keeps the data on that computer."
			),
		]),
		warning_text: paragraphs([
			__(
				"Guests and members write prayer requests, connection cards, forms and emails. This text can hold instructions meant for the AI. Keep the AI app's setting that asks you before every change turned on, and read each change before you approve it."
			),
		]),
		warning_turning_on: paragraphs([
			__(
				"Turning AI on does not open MCP by itself. After that, a System Manager can turn on Frappe's MCP server in System Settings, on the AI Agents tab. MCP is how an AI app, such as Claude or ChatGPT, connects to this site."
			),
			__(
				"Only a Church Manager, a System Manager or a person with the Church AI User role can connect an AI app. A System Manager gives that role on the person's User record. Give it only to people you trust to send what they can read to an AI company."
			),
			__(
				"Removing the role stops the person's AI app from using MCP at once. An app that is already connected keeps working with the REST API until you delete the person's tokens."
			),
		]),
		warning_flow_agents: paragraphs([
			__(
				"On this site, turning AI on starts Flow, Frappe's AI agents, at once. People with the Flow User role, and System Managers, can chat with AI agents in the desk. A chat works with the person's own permissions and sends what it reads to the AI model that a System Manager added in Flow. Each Flow trigger that is on can start chats, and those chats approve their own changes."
			),
			__(
				"Frappe's general assistant agent, frappe/Flow, can add, change and delete every record that the person can. To stop that, clear Enabled on it in the Flow Agent list right after you turn AI on. While AI is off, a System Manager cannot open an agent."
			),
		]),
		warning_turning_off:
			paragraphs([
				__(
					"Turning AI off closes MCP. It does not sign out the AI apps that are already connected: their tokens still work with the REST API until you revoke them. It does not stop API keys either."
				),
				...only_with_flow([
					__(
						"Turning AI off also stops new Flow chats, Flow triggers and new knowledge sources, but not a reply that Flow is writing at that moment, and after that only Administrator can stop the reply. So to stop a reply that changes records, first clear Enabled on its agent in the Flow Agent list, because Flow checks it before the agent uses each tool. Then turn AI off. People can still read their earlier chats, and Administrator can still continue them."
					),
				]),
			]) +
			`<p><a href="/app/oauth-bearer-token" style="text-decoration: underline">${escape(
				__("Revoke a connected app in the OAuth Bearer Token list")
			)}</a></p>`,
		warning_no_switch: bullets([
			__(
				"Calls to the REST API with an API key. A key gives a script or an AI tool its owner's access, so a System Manager makes keys only for people they trust."
			),
			__(
				"Staff who copy and paste church data into an AI tool. Only your church's policy stops this."
			),
			__(
				"AI in other apps on this site, such as Frappe Builder, Frappe Assistant Core and Raven."
			),
			__("Webhooks and Server Scripts that send records to an AI service."),
			__("Browser extensions and browser assistants that read the desk page."),
			...only_with_flow([
				__(
					"The daily copy of a Flow knowledge source that already reads church records or a blocked DocType. The AI Access panel lists each one. Delete it, or untick its Auto Sync."
				),
			]),
		]),
		warning_knowledge: paragraphs([
			__(
				"A Flow knowledge source with the Source Type DocType copies records into a knowledge base: each record of its Reference DocType that matches its Filters, with the fields in its Content Fields. Flow does not check who may read each record. It sends the copied text to the embedding model that is set in Flow, and copies the changed records again at each sync, each day when Auto Sync is on."
			),
			__(
				"Everyone who chats with an agent that has the knowledge base can read the copied text, whatever their own permissions. A chat and an AI app work with the person's own permissions, but a knowledge base does not. So set Roles on each agent that has a knowledge base. An agent with no Roles is open to every Flow User, and System Managers can use every agent. A sub-agent works for everyone who can use the agent that has it, so set Roles on that agent too."
			),
			__(
				"Churchit refuses a new knowledge source, or a change that makes one read, on a DocType in the Blocked from Flow Knowledge list below. A source that is already saved keeps its daily copy: the AI Access panel lists it."
			),
			__(
				"The list starts with the recommended DocTypes: the Churchit and Frappe records that hold data about people, and Flow's own records of chats and knowledge. You can remove a DocType or add one. A source on a Churchit or recommended DocType that is not in the list saves, with a warning. A source on any other DocType saves with no warning, so add each DocType that holds data about people, such as those of other apps. The Use the Recommended List button adds back each recommended DocType that is missing, and keeps the ones you added. Press it again after each update of Churchit or Frappe."
			),
		]),
	};
}

function paragraphs(texts) {
	return texts.map((text) => `<p>${escape(text)}</p>`).join("");
}

function bullets(texts) {
	return `<ul>${texts.map((text) => `<li>${escape(text)}</li>`).join("")}</ul>`;
}

function show_exposure(frm) {
	const wrapper = frm.get_field("exposure_html").$wrapper;
	frappe
		.xcall("churchit.ai.exposure.get_exposure", {}, "GET")
		.then((lines) => wrapper.html(exposure_html(lines)));
}

function exposure_html(lines) {
	return `
		<table class="table table-bordered">
			<thead><tr>
				<th>${escape(__("AI Access"))}</th>
				<th>${escape(__("State"))}</th>
				<th>${escape(__("Set In"))}</th>
			</tr></thead>
			<tbody>${lines.map(exposure_row).join("")}</tbody>
		</table>`;
}

function exposure_row(line) {
	const owner = escape(__(line.owner));
	return `<tr>
		<td>${escape(line.surface)}<div class="text-muted small">${escape(line.note)}</div></td>
		<td class="text-nowrap"><span class="indicator-pill ${PILL_COLORS[line.open]}">${escape(
		line.state
	)}</span></td>
		<td>${line.link ? `<a href="${escape(line.link)}">${owner}</a>` : owner}</td>
	</tr>`;
}
