# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The master AI switch over Flow, Frappe's AI agents.

While AI is off, no Flow chat or trigger can start, only Administrator can continue an old chat, and
no save makes Flow read a knowledge source; an install, a migrate or a patch still writes the
agents, tools and triggers that apps ship. While AI is on, a person's new chat asks before each
change. No save, in an update too, makes Flow copy church records into its knowledge, because Flow
reads them without checking who may read each one. These hooks work on Flow's documents and never
import frappe.flow; a Frappe without Flow never calls them.
"""

import frappe
from frappe import _
from frappe.permissions import push_perm_check_log

from churchit.ai.switch import is_ai_on

# Doctypes that guests and members write. Their text can hold instructions for an agent.
GUEST_DOCTYPES = (
	"Alms Request",
	"Care Request",
	"Comment",
	"Communication",
	"Connection Card",
	"Form Response",
	"Function Sign-Up",
	"Group File",
	"Group Join Request",
	"Ministry Team Assignment",
	"Ministry Team Block",
	"Online Donation",
	"Person",
	"Prayer",
	"Prayer Request",
	"Room Booking",
)
# Frappe doctypes that hold church people's data or copies of church records.
PEOPLE_DOCTYPES = (
	"Address",
	"Comment",
	"Communication",
	"Contact",
	"Deleted Document",
	"Email Queue",
	"File",
	"ToDo",
	"User",
	"Version",
)
# What a knowledge source reads. Flow reads the source again when one of them changes.
READ_FIELDS = ("source_type", "content", "file", "url", "reference_doctype", "filters", "content_fields")


def is_updating() -> bool:
	"""True while an install, a migrate or a patch runs. Flow writes the rows that apps ship then."""
	return bool(frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch)


def is_flow_off() -> bool:
	"""True while AI is off, except in an install, a migrate or a patch, which must not stop."""
	return not is_ai_on() and not is_updating()


def is_flow_allowed() -> bool:
	"""False while Flow is off. Frappe shows the reason when a person's own check fails."""
	if is_flow_off():
		push_perm_check_log(_("AI is turned off on this site."))
		return False
	return True


def has_agent_permission(doc, ptype=None, user=None) -> bool:
	"""Flow Agent has_permission: while AI is off, nobody may use, open or change an agent.

	Flow checks that the person may read the agent when a chat starts and at every turn.
	"""
	return is_flow_allowed()


def agent_query_conditions(user=None, doctype=None) -> str:
	"""Flow Agent permission_query_conditions: while AI is off, no list shows an agent."""
	return "1 = 0" if is_flow_off() else ""


def has_session_permission(doc, ptype=None, user=None) -> bool:
	"""Flow Session has_permission: while AI is off, nobody starts or continues a chat.

	People still read their past chats. Frappe never asks this hook about Administrator.
	"""
	return ptype not in ("create", "write") or is_flow_allowed()


def check_new_session(doc, method=None) -> None:
	"""Flow Session before_insert: refuse a new chat while AI is off, and start a person's chat in Ask.

	Flow inserts every session with ignore_permissions, so the refusal also stops Administrator and
	triggers. Flow's default, Auto, lets a second AI model approve changes; the person may still
	choose another mode in the chat.
	"""
	if is_flow_off():
		refuse_because_ai_is_off(frappe.PermissionError)
	if doc.source == "Manual" and doc.approval_mode == "Auto":
		doc.approval_mode = "Ask"


def check_trigger(doc, method=None) -> None:
	"""Flow Trigger before_validate: refuse an enabled trigger while AI is off; warn about a risky one
	while it is on.

	It runs before Flow's own validate, which would refuse a named Run As with its own message while AI
	is off. An update, and Flow's own sync of an app's trigger (system-generated, saved with
	ignore_permissions) when the first model arrives, save the triggers that apps ship as they are; an
	enabled one cannot start a chat while AI is off. The exposure panel lists each one to check.
	"""
	if is_updating() or (doc.is_system_generated and doc.flags.ignore_permissions):
		return
	if is_ai_on():
		warn_about_trigger(doc)
	elif doc.enabled:
		refuse_because_ai_is_off()


def warn_about_trigger(doc) -> None:
	"""Warn, without refusing, about an enabled trigger that needs a check."""
	if not doc.enabled:
		return
	for warning in get_trigger_warnings(doc):
		frappe.msgprint(warning, _("Check This Trigger"), indicator="orange")


def get_trigger_warnings(trigger) -> list[str]:
	"""Why a trigger needs a check: it watches text that guests or members write, or it runs as
	Administrator. A trigger's chat approves its own changes."""
	warnings = []
	if trigger.target_doctype in GUEST_DOCTYPES:
		warnings.append(
			_(
				"Guests and members write {0} records, and their text can hold instructions for the AI. "
				"A trigger's chat approves every change by itself, so give its agent only tools that read."
			).format(_(trigger.target_doctype))
		)
	if (trigger.run_as or trigger.owner) == "Administrator":
		warnings.append(
			_(
				"This trigger runs as Administrator, who can read and change everything. Set Run As to a "
				"user with only the roles that the trigger needs."
			)
		)
	return warnings


def check_knowledge_source(doc, method=None) -> None:
	"""Flow Knowledge Source validate: no save makes Flow read church records, or read while AI is off.

	Flow reads a DocType source with frappe.get_all and gives its text to everyone who chats with an
	agent that has the knowledge base. It sends the text to the embedding model before it saves
	chunks, so a save is the last place to refuse. A rename or Auto Sync turned off still saves. An
	install, a migrate or a patch skips only the AI-off refusal, so an app that copies church records
	into Flow fails its update.
	"""
	if not is_new_reading(doc):
		return
	if doc.source_type == "DocType" and is_church_doctype(doc.reference_doctype):
		frappe.throw(
			_(
				"Flow copies {0} records into its knowledge without checking who may read them, so a "
				"knowledge source cannot read church records."
			).format(_(doc.reference_doctype)),
			title=_("Church Records"),
		)
	if is_flow_off():
		refuse_because_ai_is_off()


def is_church_doctype(doctype: str | None) -> bool:
	"""True for a doctype of a churchit module, or a Frappe doctype that holds church people's data."""
	if doctype in PEOPLE_DOCTYPES:
		return True
	module = doctype and frappe.db.get_value("DocType", doctype, "module")
	return bool(module) and frappe.db.get_value("Module Def", module, "app_name") == "churchit"


def is_new_reading(doc) -> bool:
	"""True when saving the source makes Flow read it and send its text to the embedding model again."""
	if doc.is_new() or (doc.auto_sync and doc.has_value_changed("auto_sync")):
		return True
	return any(doc.has_value_changed(field) for field in READ_FIELDS)


def refuse_because_ai_is_off(exception: type[Exception] = frappe.ValidationError) -> None:
	"""Raise with the sentence of switch.require_ai, shown to the person. Flow's sync of an app's row
	skips a ValidationError and goes on."""
	frappe.throw(_("AI is turned off on this site."), exception, title=_("AI Is Off"))
