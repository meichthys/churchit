# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The master AI switch and who may connect an AI app.

Church AI Settings decides whether churchit uses AI at all. While it is off, every churchit AI
feature refuses and Frappe's MCP server stays closed. The switch never turns MCP on: System Settings
stays the only owner of enable_mcp. An AI app works with its user's permissions, so churchit limits
who may sign one in (AI_ROLES) and warns where people decide.
"""

import json
from urllib.parse import quote, urlencode

import frappe
from frappe import _
from frappe.core.doctype.role.role import get_info_based_on_role
from frappe.core.doctype.system_settings.system_settings import clear_system_settings_cache
from frappe.desk.utils import slug
from frappe.utils import escape_html, get_link_to_form, get_url_to_list, get_url_to_report

SETTINGS = "Church AI Settings"
AI_APPS_REPORT = "Connected AI Apps"
AI_ROLES = ("Church Manager", "System Manager", "Church AI User")
MCP_PATH = "/api/v2/mcp"
# Roles that Frappe gives every signed-in user ("Guest", "All") or every desk user ("Desk User").
EVERYONE_ROLES = ("Guest", "All", "Desk User")


def is_ai_on() -> bool:
	"""True while Church AI Settings is enabled.

	Off until migrate has synced the doctype: pre-model-sync patches still save records (their own
	Patch Log among them) on the schema being upgraded.
	"""
	return bool(get_setting(SETTINGS, "enabled"))


def require_ai(feature: str | None = None) -> None:
	"""Raise PermissionError while AI is off. Every churchit AI method and job asks this first."""
	if not is_ai_on():
		raise frappe.PermissionError(_("AI is turned off on this site."))


def has_flow() -> bool:
	"""True on a Frappe that ships Flow, Frappe's AI agents."""
	return bool(frappe.db.exists("DocType", "Flow Agent"))


def extend_bootinfo(bootinfo) -> None:
	"""Tell the desk whether AI is on and Flow can run churchit's agents.

	frappe.boot.churchit.ai = {"on": bool, "flow_ready": bool}. The Flow module loads only on a
	Frappe that ships Flow.
	"""
	ai = {"on": is_ai_on(), "flow_ready": False}
	if has_flow():
		from churchit.ai import flow

		ai["flow_ready"] = flow.is_ready()
	bootinfo.setdefault("churchit", {})["ai"] = ai


def refuse_mcp_while_ai_off(doc, method=None) -> None:
	"""System Settings validate: refuse a person's change of enable_mcp to 1 while AI is off.

	Only that change: every other System Settings save goes through. A save by an install, a patch or
	a migrate goes through too, so a Frappe step that opens MCP cannot stop an update;
	close_mcp_while_ai_off closes MCP again after the migrate.
	"""
	if frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_migrate:
		return
	if doc.get("enable_mcp") and doc.has_value_changed("enable_mcp") and not is_ai_on():
		frappe.throw(_("Turn on AI in Church AI Settings first."), title=_("AI Is Off"))


def close_mcp() -> bool:
	"""Set System Settings enable_mcp to 0. True when MCP was open.

	Writes the value directly, so no other app's System Settings hook runs. On a Frappe without
	enable_mcp it does nothing, and test_switch fails.
	"""
	if not get_setting("System Settings", "enable_mcp"):
		return False
	frappe.db.set_single_value("System Settings", "enable_mcp", 0)
	clear_system_settings_cache()
	return True


def close_mcp_while_ai_off() -> bool:
	"""Keep MCP closed while AI is off (after_install, after_migrate). True when it closed MCP.

	It runs after every migrate because a Frappe patch can write enable_mcp directly.
	"""
	return not is_ai_on() and close_mcp()


def close_mcp_and_tell_system_managers() -> None:
	"""Close MCP while AI is off and, when it was open, tell each System Manager (install, upgrade).

	The users of other apps on the site, such as ERPNext, lose MCP too, so somebody must know why.
	"""
	if close_mcp_while_ai_off():
		tell_system_managers_mcp_closed()


def refuse_mcp_to_other_users() -> None:
	"""auth_hooks: only AI_ROLES may use Frappe's MCP server, however they signed in.

	Frappe's MCP server takes every desk user, with a session, an API key or the token of an app
	that every desk user may sign in. Removing the role takes effect at the next request. A guest
	goes on to Frappe's own 401, which starts an AI app's sign-in.
	"""
	if frappe.request.path.rstrip("/") != MCP_PATH or frappe.session.user in ("", "Guest"):
		return
	if not set(AI_ROLES) & set(frappe.get_roles()):
		raise frappe.PermissionError(
			_("Only a Church Manager, a System Manager or a Church AI User may connect an AI app.")
		)


def limit_new_app_to_ai_roles(doc, method=None) -> None:
	"""OAuth Client before_insert: a new app with no Allowed Roles is for AI_ROLES only.

	Frappe lets a user sign in an app only when they hold one of its Allowed Roles, and gives an app
	with none "Desk User", which every desk user holds. Dynamic client registration, which every MCP
	client uses, saves an app with none. An app made with roles keeps them; existing apps keep theirs.
	"""
	if not doc.allowed_roles:
		for role in AI_ROLES:
			doc.append("allowed_roles", {"role": role})


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
		get_builder_line(),
		get_assistant_core_line(),
		get_raven_line(),
	]


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


def get_setting(doctype: str, fieldname: str) -> bool | None:
	"""A Check on a Single of Frappe or another app, or None when this site has no such field."""
	if not frappe.db.exists("DocType", doctype) or not frappe.get_meta(doctype).has_field(fieldname):
		return None
	return bool(frappe.db.get_single_value(doctype, fieldname))


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


def tell_system_managers(subject: str, message: str, document_type: str, document_name: str) -> None:
	"""Leave each System Manager a bell notice. *subject* and *message* are HTML."""
	notice = {
		"doctype": "Notification Log",
		"type": "Alert",
		"subject": subject,
		"email_content": message,
		"document_type": document_type,
		"document_name": document_name,
	}
	for user in set(get_info_based_on_role("System Manager", "name", ignore_permissions=True)):
		frappe.get_doc({**notice, "for_user": user}).insert(ignore_permissions=True)


def tell_system_managers_mcp_closed() -> None:
	"""Leave each System Manager one bell notice that churchit closed MCP."""
	tell_system_managers(
		_("Churchit turned off AI access (MCP) on this site"), get_mcp_closed_message(), SETTINGS, SETTINGS
	)


def get_mcp_closed_message() -> str:
	"""The notice of the install and the upgrade patch: why MCP closed, who else loses it and the way back."""
	paragraphs = [
		escape_html(
			_(
				"Since a Frappe 16 update in October 2026, Frappe turns on AI access (MCP) for every "
				"site. Churchit turned it off on this site and keeps it off until you turn on AI in "
				"Church AI Settings."
			)
		)
	]
	if other_apps := get_other_business_apps():
		paragraphs.append(
			escape_html(
				_("MCP is one setting for the whole site, so the users of {0} lose MCP too.").format(
					", ".join(other_apps)
				)
			)
		)
	paragraphs.append(
		_("To open MCP again, turn on AI in {0}, then tick Enable MCP in {1} on the AI Agents tab.").format(
			get_link_to_form(SETTINGS), get_link_to_form("System Settings")
		)
	)
	paragraphs.append(
		escape_html(
			_(
				"Only a Church Manager, a System Manager or a person with the Church AI User role can "
				"connect an AI app."
			)
		)
	)
	paragraphs.append(
		_(
			"Apps that registered before this update may be open to every desk user. Check the AI Access "
			"panel in {0} before you open MCP."
		).format(get_link_to_form(SETTINGS))
	)
	paragraphs.append(
		_("Nobody needs dynamic client registration while AI is off. Turn it off in {0}.").format(
			get_link_to_form("OAuth Settings")
		)
	)
	return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)


def get_other_business_apps() -> list[str]:
	"""Titles of the other apps on this site that people open from the Apps screen, such as ERPNext."""
	return [
		frappe.get_hooks("app_title", app_name=app)[0]
		for app in frappe.get_installed_apps()
		if app not in ("frappe", "churchit") and frappe.get_hooks("add_to_apps_screen", app_name=app)
	]


def tell_system_managers_of_new_ai_app(doc, method=None) -> None:
	"""OAuth Bearer Token after_insert: tell each System Manager when a person first connects an app.

	Frappe stores a new token at every hourly refresh, so only the first token of a person and app
	counts; after a revoke or a delete, a new sign-in counts again. Any OAuth app counts, because
	churchit cannot tell an AI app from another. The notice names the app's OAuth Client and never
	the token, which is the token's name. The bell notice always comes; the email needs an outgoing
	email account, and without one it is logged, because the person's sign-in must not fail.
	"""
	others = {"user": doc.user, "client": doc.client, "status": "Active", "name": ("!=", doc.name)}
	if frappe.db.exists("OAuth Bearer Token", others):
		return

	subject = _("{0} connected an app to your church site").format(escape_html(doc.user))
	message = get_ai_app_message(
		doc.user, doc.client, frappe.db.get_value("OAuth Client", doc.client, "app_name")
	)
	tell_system_managers(subject, message, "OAuth Client", doc.client)
	try:
		frappe.sendmail(
			recipients=get_info_based_on_role("System Manager", "email", ignore_permissions=True),
			subject=subject,
			message=message,
			reference_doctype="OAuth Client",
			reference_name=doc.client,
		)
	except frappe.OutgoingEmailError:
		frappe.log_error(_("Could not email System Managers that an AI app was connected"))


def get_ai_app_message(user: str, client: str, app_name: str | None) -> str:
	"""The notice of a new app: who, which app, and how to revoke it. The app chose its own name."""
	tokens = get_url_to_list("OAuth Bearer Token") + "?" + urlencode({"user": user, "client": client})
	paragraphs = [
		_("{0} connected an app, perhaps an AI app such as Claude or ChatGPT, to this site.").format(
			escape_html(user)
		),
		_("App: {0} (the name the app gave itself)").format(
			f"<strong>{escape_html(app_name or '')}</strong>"
		),
		_(
			"This app can now see and change what {0} can see and change. If you did not expect this, "
			"revoke it: {1}."
		).format(
			escape_html(user),
			f'<a href="{escape_html(tokens)}">{escape_html(_("delete its tokens"))}</a>',
		),
		_("The {0} report lists every connection.").format(
			f'<a href="{get_url_to_report(AI_APPS_REPORT, "Script Report", "OAuth Bearer Token")}">'
			f"{AI_APPS_REPORT}</a>"
		),
	]
	return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
