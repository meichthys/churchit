// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

const escape = (text) => frappe.utils.escape_html(text || "");
const EXPOSURE_ROLES = ["System Manager", "Church Manager"];
const PILL_COLORS = { true: "orange", false: "green", null: "gray" };

frappe.ui.form.on("Church AI Settings", {
	refresh(frm) {
		frm.get_field("intro_html").$wrapper.html(intro_html());
		const may_see_exposure = frappe.user.has_role(EXPOSURE_ROLES);
		frm.toggle_display("exposure_section", may_see_exposure);
		if (may_see_exposure) show_exposure(frm);
	},
});

function intro_html() {
	return `<div style="max-width: 46rem">
		<div class="form-message yellow"><div>${escape(
			__(
				"A connected AI app can see and change everything that its user can see and change. A hosted AI app sends everything it reads to the company that runs it."
			)
		)}</div></div>
		${section(__("What turning AI on does"), [
			__(
				"Turning AI on does not open MCP by itself. After that, a System Manager can turn on Frappe's MCP server in System Settings, on the AI Agents tab. MCP is how an AI app, such as Claude or ChatGPT, connects to this site."
			),
			__(
				"Only a Church Manager, a System Manager or a person with the Church AI User role can connect an AI app. A System Manager gives that role on the person's User record. Give it only to people you trust to send what they can read to an AI company."
			),
			__(
				"Removing the role stops the person's AI app from using MCP at once. An app that is already connected keeps working with the REST API until you delete the person's tokens."
			),
			__(
				"On a site with Flow, Frappe's AI agents, turning AI on starts Flow at once. People with the Flow User role, and System Managers, can chat with AI agents in the desk. A chat works with the person's own permissions and sends what it reads to the AI model that a System Manager added in Flow. Each Flow trigger that is on can start chats, and those chats approve their own changes."
			),
			__(
				"Frappe's general assistant agent, frappe/Flow, can add, change and delete every record that the person can. To stop that, clear Enabled on it in the Flow Agent list right after you turn AI on. While AI is off, a System Manager cannot open an agent."
			),
		])}
		${section(__("What a connected AI app can do"), [
			__(
				"An AI app works as the person who connected it. It can see and change everything that person can see and change in the desk. If the person can read care notes, counseling, medical notes, giving or the details of children, the AI app can read them too."
			),
			__(
				"An AI app can change records as fast as it can read them, many records in the time a person changes one."
			),
		])}
		${section(__("Where your data goes"), [
			__(
				"A hosted AI app, such as Claude, ChatGPT or Gemini, sends everything it reads to the company that runs it. That company's terms then apply to your church's data."
			),
			__(
				"A local AI model on your own computer, for example in Ollama or LM Studio, keeps the data on that computer."
			),
		])}
		${section(__("Text that other people write"), [
			__(
				"Guests and members write prayer requests, connection cards, forms and emails. This text can hold instructions meant for the AI. Keep the AI app's setting that asks you before every change turned on, and read each change before you approve it."
			),
		])}
		${section(__("Turning AI off"), [
			__(
				"Turning AI off closes MCP. It does not sign out the AI apps that are already connected: their tokens still work with the REST API until you revoke them. It does not stop API keys either."
			),
			__(
				"On a site with Flow, turning AI off also stops new Flow chats and Flow triggers, but not a reply that Flow is writing at that moment, and after that only Administrator can stop the reply. So to stop a reply that changes records, first clear Enabled on its agent in the Flow Agent list, because Flow checks it before the agent uses each tool. Then turn AI off. People can still read their earlier chats, and Administrator can still continue them."
			),
		])}
		<p><a href="/app/oauth-bearer-token" style="text-decoration: underline">${escape(
			__("Revoke a connected app in the OAuth Bearer Token list")
		)}</a></p>
		<p class="bold">${escape(__("What no switch stops"))}</p>
		<ul>${[
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
			__(
				"On a site with Flow, the daily copy of a Flow knowledge source on church records that was added before Churchit refused them. The AI Access panel lists each one. Delete it, or untick its Auto Sync."
			),
		]
			.map((item) => `<li>${escape(item)}</li>`)
			.join("")}</ul></div>`;
}

function section(title, texts) {
	return `<p class="bold">${escape(title)}</p>${paragraphs(texts)}`;
}

function paragraphs(texts) {
	return texts.map((text) => `<p>${escape(text)}</p>`).join("");
}

function show_exposure(frm) {
	const wrapper = frm.get_field("exposure_html").$wrapper;
	frappe
		.xcall("churchit.ai.switch.get_exposure", {}, "GET")
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
