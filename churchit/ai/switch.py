# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The master AI switch and who may connect an AI app.

Church AI Settings decides whether churchit uses AI at all. While it is off, every churchit AI
feature refuses and Frappe's MCP server stays closed. The switch never turns MCP on: System Settings
stays the only owner of enable_mcp. An AI app works with its user's permissions, so churchit limits
who may sign one in (AI_ROLES) and warns where people decide: the notices to System Managers here,
the AI Access panel in exposure.py.
"""

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.core.doctype.role.role import get_info_based_on_role
from frappe.core.doctype.system_settings.system_settings import clear_system_settings_cache
from frappe.utils import escape_html, get_link_to_form, get_url_to_list, get_url_to_report

SETTINGS = "Church AI Settings"
AI_APPS_REPORT = "Connected AI Apps"
AI_ROLES = ("Church Manager", "System Manager", "Church AI User")
MCP_PATH = "/api/v2/mcp"


def is_ai_on() -> bool:
	"""True while Church AI Settings is enabled.

	Off until migrate has synced the doctype: pre-model-sync patches still save records (their own
	Patch Log among them) on the schema being upgraded.
	"""
	return bool(get_setting(SETTINGS, "enabled"))


def require_ai(feature: str | None = None) -> None:
	"""Refuse with PermissionError while AI is off, and tell the person why. Every churchit AI method
	and job asks this first."""
	if not is_ai_on():
		frappe.throw(_("AI is turned off on this site."), frappe.PermissionError, title=_("AI Is Off"))


def has_flow() -> bool:
	"""True on a Frappe that ships Flow, Frappe's AI agents."""
	return bool(frappe.db.exists("DocType", "Flow Agent"))


def extend_bootinfo(bootinfo) -> None:
	"""Tell the desk whether AI is on, Flow is present and Flow can run churchit's agents.

	frappe.boot.churchit.ai = {"on": bool, "flow": bool, "flow_ready": bool}. The Flow module loads
	only on a Frappe that ships Flow.
	"""
	ai = {"on": is_ai_on(), "flow": has_flow(), "flow_ready": False}
	if ai["flow"]:
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


def get_setting(doctype: str, fieldname: str) -> bool | None:
	"""A Check on a Single of Frappe or another app, or None when this site has no such field."""
	if not frappe.db.exists("DocType", doctype) or not frappe.get_meta(doctype).has_field(fieldname):
		return None
	return bool(frappe.db.get_single_value(doctype, fieldname))


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
