# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The AI Access panel on Church AI Settings: each way AI can reach this site, one line each.

It only reads, and it works while AI is off. It imports switch, flow_switch, flow_models and guide, so
none of them may import it.
"""

import json
from urllib.parse import quote, urlencode

import frappe
from frappe import _
from frappe.desk.utils import slug

from churchit.ai.flow_models import DEFAULT_LABEL, LABEL_FIELD, UNSAFE_LABELS
from churchit.ai.flow_switch import get_blocked_knowledge_doctypes, get_trigger_warnings, is_church_doctype
from churchit.ai.guide import has_guide_pointer
from churchit.ai.switch import AI_ROLES, SETTINGS, get_setting, has_flow, is_ai_on

# Roles that Frappe gives every signed-in user ("Guest", "All") or every desk user ("Desk User").
EVERYONE_ROLES = ("Guest", "All", "Desk User")


@frappe.whitelist(methods=["GET"])
def get_exposure() -> list[dict]:
	"""Each way AI can reach this site, for the panel on Church AI Settings. Reads only.

	For System Managers and Church Managers; it works while AI is off. Each line has surface, state,
	open (True, False, or None when unknown), owner (the doctype that owns the setting), link and
	note. Only a System Manager sees which apps hold tokens and how many people hold API keys,
	because Frappe lets only them read those records.
	"""
	frappe.only_for(("System Manager", "Church Manager"))
	is_system_manager = "System Manager" in frappe.get_roles()
	return [
		make_line(
			_("Churchit AI"),
			is_ai_on(),
			SETTINGS,
			_("Churchit's own AI features. None of them sends data in this release."),
		),
		make_line(
			_("Frappe MCP server"),
			get_setting("System Settings", "enable_mcp"),
			"System Settings",
			_("Lets a person connect their own AI app, such as Claude or ChatGPT, with their permissions."),
		),
		get_guide_pointer_line(is_system_manager),
		make_line(
			_("Dynamic client registration"),
			get_setting("OAuth Settings", "enable_dynamic_client_registration"),
			"OAuth Settings",
			_("Lets any app register itself without a sign-in. Nobody needs it while AI is off."),
		),
		make_line(
			_("Sign-in metadata for apps"),
			get_setting("OAuth Settings", "show_auth_server_metadata"),
			"OAuth Settings",
			_("Tells AI apps where to sign in."),
		),
		get_ai_people_line() if is_system_manager else ask_line(_("People who may connect an AI app")),
		*(get_open_app_lines() if is_system_manager else [ask_line(_("Apps open to every desk user"))]),
		*(get_connected_app_lines() if is_system_manager else [ask_line(_("Connected apps"))]),
		get_api_key_line() if is_system_manager else ask_line(_("API keys")),
		*get_flow_lines(is_system_manager),
		*get_flow_model_lines(is_system_manager),
		get_builder_line(),
		get_assistant_core_line(),
		get_raven_line(),
	]


def get_guide_pointer_line(is_system_manager: bool) -> dict:
	"""Whether System Settings Agent Instructions point AI apps to the Churchit guide.

	While AI is on and the sentence is missing, a System Manager gets the button that adds it.
	"""
	has_pointer = has_guide_pointer()
	line = make_line(
		_("Agent Instructions"),
		not has_pointer,
		"System Settings",
		_(
			"Frappe gives these instructions to every AI app that connects. The Churchit sentence there "
			"tells the app to read Churchit's rules first: church scoping, private fields and drafts."
		),
		state=_("Names the Churchit guide") if has_pointer else _("No Churchit guide"),
	)
	if is_system_manager and not has_pointer and is_ai_on():
		line.update(action="add_guide_pointer", button=_("Add the Churchit Sentence"))
	return line


def make_line(
	surface: str,
	is_open: bool | None,
	owner: str | None = None,
	note: str = "",
	state: str | None = None,
	link: str | None = None,
) -> dict:
	"""One line of the exposure panel. Without *link*, it links to the owner when that doctype exists."""
	if not link and owner and frappe.db.exists("DocType", owner):
		link = f"/app/{slug(owner)}"
	return {
		"surface": surface,
		"state": state or {True: _("On"), False: _("Off"), None: _("Unknown")}[is_open],
		"open": is_open,
		"owner": owner or "",
		"link": link,
		"note": note,
	}


def ask_line(surface: str) -> dict:
	return make_line(surface, None, state=_("Ask a System Manager"))


def count_people(count: int) -> str:
	return _("1 person") if count == 1 else _("{0} people").format(count)


def get_ai_people_line() -> dict:
	"""How many enabled desk users hold one of AI_ROLES, with a link to the list of them.

	A member with the role is left out: Frappe's MCP server is for desk users only.
	"""
	users = frappe.get_list(
		"User",
		filters=[
			["enabled", "=", 1],
			["user_type", "=", "System User"],
			["Has Role", "role", "in", AI_ROLES],
		],
		pluck="name",
		distinct=True,
		limit=0,
	)
	return make_line(
		_("People who may connect an AI app"),
		bool(users),
		"User",
		_(
			"Church Managers, System Managers and the people with the Church AI User role. A System "
			"Manager gives that role on the person's User record."
		),
		state=count_people(len(users)),
		link="/app/user?"
		+ urlencode({"enabled": 1, "user_type": "System User", "role": json.dumps(["in", AI_ROLES])}),
	)


def get_open_app_lines() -> list[dict]:
	"""One line per OAuth Client that every desk user may sign in, with a link to its form.

	Frappe gives a client with no Allowed Roles "Desk User", and an older client "All".
	"""
	clients = frappe.get_list(
		"OAuth Client", fields=["name", "app_name", "allowed_roles.role as role"], limit=0
	)
	roles = {}
	for client in clients:
		roles.setdefault((client.name, client.app_name), set()).add(client.role)

	lines = [
		make_line(
			_("App open to every desk user: {0}").format(app_name or name),
			True,
			"OAuth Client",
			_(
				"Any desk user, volunteers included, may sign in this app. If it is an AI app, set its "
				"Allowed Roles to Church Manager, System Manager and Church AI User."
			),
			state=_("Every user") if client_roles & {"Guest", "All"} else _("Every desk user"),
			link=f"/app/oauth-client/{quote(name)}",
		)
		for (name, app_name), client_roles in roles.items()
		if client_roles & {*EVERYONE_ROLES, None}
	]
	return lines or [make_line(_("Apps open to every desk user"), False, "OAuth Client", state=_("None"))]


def get_connected_app_lines() -> list[dict]:
	"""One line per app with an active token, and how many people it acts for. App names come from the apps."""
	tokens = frappe.get_list(
		"OAuth Bearer Token", filters={"status": "Active"}, fields=["client", "user"], distinct=True, limit=0
	)
	people = {}
	for token in tokens:
		people.setdefault(token.client, set()).add(token.user)
	if not people:
		return [make_line(_("Connected apps"), False, "OAuth Bearer Token", state=_("None"))]

	names = dict(
		frappe.get_list(
			"OAuth Client", filters={"name": ("in", list(people))}, fields=["name", "app_name"], as_list=True
		)
	)
	return [
		make_line(
			_("Connected app: {0}").format(names.get(client) or client),
			True,
			"OAuth Bearer Token",
			_("The app chose this name. Revoke it by deleting its tokens."),
			state=count_people(len(users)),
		)
		for client, users in people.items()
	]


def get_api_key_line() -> dict:
	users = frappe.get_list("User", filters={"enabled": 1, "api_key": ("is", "set")}, pluck="name", limit=0)
	return make_line(
		_("API keys"),
		bool(users),
		"User",
		_(
			"A key gives a script or an AI tool its owner's access through REST, which no switch stops. "
			"Make keys only for people you trust."
		),
		state=count_people(len(users)),
	)


def get_flow_lines(is_system_manager: bool) -> list[dict]:
	"""Flow, Frappe's AI agents: whether this Frappe has it, who may chat, how a chat asks, and what
	reads or starts by itself. Flow lets only System Managers read knowledge sources and triggers."""
	if not has_flow():
		return [
			make_line(
				_("Flow"),
				False,
				note=_("Frappe's AI agents come with a later version of Frappe."),
				state=_("Not available"),
			)
		]
	return [
		make_line(
			_("Flow"),
			is_ai_on(),
			SETTINGS,
			_(
				"Frappe's AI agents in the desk. A chat works with the person's own permissions. While AI "
				"is off, Flow refuses new chats, new messages except Administrator's, triggers and new "
				"knowledge sources. It still shows its chat button to Flow Users, and then says that no "
				"agent is enabled."
			),
		),
		get_flow_people_line() if is_system_manager else ask_line(_("People who may use Flow")),
		make_line(
			_("Flow chats ask before changes"),
			False,
			note=_(
				"A new chat starts in Ask, so Flow asks the person before each change. The person can "
				"switch a chat to Auto, where a second AI model approves changes, or to Auto-approve."
			),
			state=_("Ask"),
		),
		*(
			get_flow_knowledge_lines()
			if is_system_manager
			else [ask_line(_("Flow knowledge from church records"))]
		),
		*(get_flow_trigger_lines() if is_system_manager else [ask_line(_("Flow triggers"))]),
	]


def get_flow_people_line() -> dict:
	"""How many enabled desk users may chat with Flow: Flow Users and System Managers."""
	roles = ("Flow User", "System Manager")
	users = frappe.get_list(
		"User",
		filters=[["enabled", "=", 1], ["user_type", "=", "System User"], ["Has Role", "role", "in", roles]],
		pluck="name",
		distinct=True,
		limit=0,
	)
	return make_line(
		_("People who may use Flow"),
		bool(users),
		"User",
		_(
			"Flow Users and System Managers. A System Manager gives the Flow User role on the person's "
			"User record."
		),
		state=count_people(len(users)),
		link="/app/user?"
		+ urlencode({"enabled": 1, "user_type": "System User", "role": json.dumps(["in", roles])}),
	)


def get_flow_knowledge_lines() -> list[dict]:
	"""One line per Flow knowledge source on church records or on a blocked doctype, which says whether
	Church AI Settings blocks the doctype."""
	blocked = get_blocked_knowledge_doctypes()
	sources = frappe.get_list(
		"Flow Knowledge Source",
		filters={"source_type": "DocType"},
		fields=["name", "title", "reference_doctype"],
		limit=0,
	)
	lines = [
		get_flow_knowledge_line(source, source.reference_doctype in blocked)
		for source in sources
		if source.reference_doctype in blocked or is_church_doctype(source.reference_doctype)
	]
	return lines or [
		make_line(_("Flow knowledge from church records"), False, "Flow Knowledge Source", state=_("None"))
	]


def get_flow_knowledge_line(source, is_blocked: bool) -> dict:
	"""The line of one source. A source on a blocked doctype was made before the block; one that is not
	blocked saved with a warning."""
	if is_blocked:
		note = _(
			"It reads {0}, which Church AI Settings blocks from Flow knowledge, but it was made before the "
			"block. Flow copied these records without checking who may read them, and shows them to "
			"everyone who chats with an agent that has this knowledge. With Auto Sync on, Flow copies "
			"them again each day, even while AI is off. Delete this source."
		)
	else:
		note = _(
			"It reads {0}, which Church AI Settings does not block. Everyone who uses an agent with this "
			"knowledge can read the copied fields of each record that the source reads, whatever their own "
			"permissions, and Flow sends the text to the embedding model. With Auto Sync on, Flow copies "
			"the records again each day, even while AI is off. Set Roles on each agent that has this "
			"knowledge and on each agent that has one of them as a sub-agent, or delete this source."
		)
	return make_line(
		_("Flow knowledge from church records: {0}").format(source.title),
		True,
		"Flow Knowledge Source",
		note.format(_(source.reference_doctype)),
		state=_("Blocked") if is_blocked else _("Not blocked"),
		link=f"/app/flow-knowledge-source/{quote(source.name)}",
	)


def get_flow_trigger_lines() -> list[dict]:
	"""How many Flow Triggers are enabled, an app's included, and one line per enabled trigger that
	needs a check. An update and Flow's own sync save an app's trigger without the warning."""
	triggers = frappe.get_list(
		"Flow Trigger",
		filters={"enabled": 1},
		fields=["name", "title", "target_doctype", "run_as", "owner"],
		order_by="title",
		limit=0,
	)
	lines = [
		make_line(
			_("Flow triggers"),
			bool(triggers),
			"Flow Trigger",
			_(
				"A trigger starts a chat by itself when a record changes or on a schedule, and the chat "
				"approves every change by itself. While AI is off, an enabled trigger, even one that an "
				"app turned on, logs an error instead of starting a chat. It starts chats again as soon as "
				"AI is on."
			),
			state=_("{0} enabled").format(len(triggers)) if triggers else _("None"),
			link="/app/flow-trigger?enabled=1",
		)
	]
	for trigger in triggers:
		if warnings := get_trigger_warnings(trigger):
			lines.append(
				make_line(
					_("Flow trigger to check: {0}").format(trigger.title),
					True,
					"Flow Trigger",
					" ".join(warnings),
					link=f"/app/flow-trigger/{quote(trigger.name)}",
				)
			)
	return lines


def get_flow_model_lines(is_system_manager: bool) -> list[dict]:
	"""One line per enabled Flow Model with its Privacy Label, open for Unknown and May train.

	Nothing on a Frappe without Flow. Flow lets only System Managers and Flow Users read a model.
	"""
	if not has_flow():
		return []
	if not is_system_manager:
		return [ask_line(_("Flow models"))]

	fields = ["name", "embedding"]
	if frappe.get_meta("Flow Model").has_field(LABEL_FIELD):  # the first migrate adds it
		fields.append(LABEL_FIELD)

	models = frappe.get_list("Flow Model", filters={"enabled": 1}, fields=fields, order_by="name", limit=0)
	if not models:
		return [make_line(_("Flow models"), False, "Flow Model", state=_("None enabled"))]

	notes = {
		DEFAULT_LABEL: _(
			"Nobody has said who sees what this model is sent. Set its Privacy Label from the provider's terms."
		),
		"May train": _("The provider may train on what this model is sent. Do not use it with church data."),
	}
	lines = []
	for model in models:
		label = model.get(LABEL_FIELD) or DEFAULT_LABEL
		surface = _("Flow embedding model: {0}") if model.embedding else _("Flow model: {0}")
		lines.append(
			make_line(
				surface.format(model.name),
				label in UNSAFE_LABELS,
				"Flow Model",
				notes.get(label, ""),
				state=_(label),
				link=f"/app/flow-model/{quote(model.name)}",
			)
		)
	return lines


def get_builder_line() -> dict:
	surface = _("Frappe Builder AI")
	if "builder" not in frappe.get_installed_apps():
		return make_line(surface, False, state=_("Not installed"))
	note = _(
		"Builder's agent can read private Person fields. Disable every Builder AI Provider and clear "
		"the key in Builder Settings."
	)
	if not frappe.db.exists("DocType", "Builder AI Provider"):
		return make_line(surface, None, note=note)
	is_open = bool(frappe.db.exists("Builder AI Provider", {"enabled": 1})) or bool(
		get_setting("Builder Settings", "ai_api_key")
	)
	return make_line(surface, is_open, "Builder AI Provider", note)


def get_assistant_core_line() -> dict:
	surface = _("Frappe Assistant Core")
	if "frappe_assistant_core" not in frappe.get_installed_apps():
		return make_line(surface, False, state=_("Not installed"))
	return make_line(
		surface,
		True,
		"Assistant Core Settings",
		_("It runs its own MCP server, which no switch here or in System Settings closes. Uninstall it."),
		state=_("Installed"),
	)


def get_raven_line() -> dict:
	surface = _("Raven AI")
	if "raven" not in frappe.get_installed_apps():
		return make_line(surface, False, state=_("Not installed"))
	return make_line(
		surface,
		get_setting("Raven Settings", "enable_ai_integration"),
		"Raven Settings",
		_("Deprecated. Keep it off."),
	)
