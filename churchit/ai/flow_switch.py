# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The master AI switch over Flow, Frappe's AI agents, and the doctypes that Flow knowledge may not read.

While AI is off, no Flow chat or trigger can start, only Administrator can continue an old chat, and
no save makes Flow read a knowledge source; an install, a migrate or a patch still writes the
agents, tools and triggers that apps ship. While AI is on, a person's new chat asks before each
change. No save, in an update too, makes Flow copy a doctype that Church AI Settings blocks from Flow
knowledge, because Flow reads its records without checking who may read each one; a source on other
church records saves with a warning. These hooks work on Flow's documents and never import
frappe.flow; a Frappe without Flow never calls them. The blocked list works on every Frappe.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.model import table_fields
from frappe.permissions import push_perm_check_log

from churchit.ai.switch import SETTINGS, is_ai_on

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
	"Access Log",
	"Activity Log",
	"Address",
	"Comment",
	"Communication",
	"Contact",
	"Data Import Log",
	"Deleted Document",
	"Email Group Member",
	"Email Queue",
	"Error Log",
	"Event",
	"File",
	"Notification Log",
	"ToDo",
	"User",
	"Version",
)
# Flow's own records of chats, memories and knowledge: what each person read with their own
# permissions, and what each knowledge source copied.
FLOW_DATA_DOCTYPES = (
	"Flow Agent Memory",
	"Flow Knowledge Chunk",
	"Flow Run",
	"Flow Session",
	"Flow Session Attachment",
	"Flow Session Message",
)
# The doctypes whose records are people. A churchit doctype that links to one holds data about people.
PERSON_LINKS = ("Contact", "Family", "Person", "User")
# Churchit doctypes that link to people but hold public content or setup.
PUBLIC_AND_SETUP_DOCTYPES = (
	"Follow-up Step",
	"Ministry",
	"Room Approver",
	"Sermon",
	"Sermon Presentation",
	"Sermon Series",
)
# Churchit doctypes about people that link to no person: a Collection totals each person's gifts, a
# Missionary can serve in a closed country and the Expense of its support names it, each import row
# is a person or a gift from another system, a Church Email holds the message to the people it names,
# a Group File is only for a group's members, and a Financial Transaction names its giver through a
# Dynamic Link.
SENSITIVE_DOCTYPES = (
	"Breeze Import",
	"Church Email",
	"Collection",
	"Expense",
	"Financial Transaction",
	"Giving Import",
	"Group File",
	"Missionary",
	"People Import",
	"Planning Center Import",
	"Rock RMS Import",
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
	"""Flow Knowledge Source validate: no save makes Flow read a blocked doctype, or read while AI is
	off; a source on church records that are not blocked saves with a warning.

	Flow reads a DocType source with frappe.get_all and gives its text to everyone who chats with an
	agent that has the knowledge base, or with an agent that has that agent as a sub-agent. It sends
	the text to the embedding model before it saves chunks, so a save is the last place to refuse. A
	rename or Auto Sync turned off still saves. An install, a migrate or a patch skips only the AI-off
	refusal, so an app that copies a blocked doctype into Flow fails its update; when it does so while
	Flow syncs its agents, Flow skips those agents and logs why.
	"""
	if not is_new_reading(doc):
		return
	reads_doctype = doc.source_type == "DocType"
	if reads_doctype and doc.reference_doctype in get_blocked_knowledge_doctypes():
		frappe.throw(
			_(
				"Church AI Settings blocks {0} from Flow knowledge, because Flow copies its records "
				"without checking who may read them."
			).format(_(doc.reference_doctype)),
			title=_("Blocked from Flow Knowledge"),
		)
	if is_flow_off():
		refuse_because_ai_is_off()
	if reads_doctype and is_church_doctype(doc.reference_doctype):
		frappe.msgprint(
			_(
				"Flow copies the content fields of each {0} record that this source reads, and everyone "
				"who uses an agent with this knowledge can read them, whatever their own permissions. Flow "
				"also sends the text to the embedding model. Set Roles on each agent that has this "
				"knowledge, so that only the right people can use it. A sub-agent works for everyone who "
				"can use the agent that has it, so set Roles on that agent too."
			).format(_(doc.reference_doctype)),
			_("Check This Knowledge Source"),
			indicator="orange",
		)


def get_blocked_knowledge_doctypes() -> set[str]:
	"""The doctypes in Blocked from Flow Knowledge on Church AI Settings."""
	return frappe.get_single(SETTINGS).blocked_doctypes


def is_church_doctype(doctype: str | None) -> bool:
	"""True for a doctype of a churchit module, or a Frappe or Flow doctype that holds church people's
	data (get_frappe_people_doctypes)."""
	if doctype in get_frappe_people_doctypes():
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


def get_recommended_knowledge_doctypes() -> list[str]:
	"""The doctypes that Blocked from Flow Knowledge recommends: the churchit doctypes that hold data
	about people, and Frappe's and Flow's (get_frappe_people_doctypes).

	A churchit doctype holds data about people when it is or links to one of PERSON_LINKS, links to
	such a doctype (one level), is in SENSITIVE_DOCTYPES, or is a child table of one of these. Settings
	and PUBLIC_AND_SETUP_DOCTYPES are left out. The rule reads each doctype's fields, Custom Fields
	included, so it finds a new doctype by itself. Flow can read a child table on its own.
	"""
	doctypes = frappe.get_all(
		"DocType",
		filters={
			"module": ("in", frappe.get_module_list("churchit")),
			"issingle": 0,
			"name": ("not in", PUBLIC_AND_SETUP_DOCTYPES),
		},
		pluck="name",
	)
	people = {*PERSON_LINKS}
	links = get_field_options(doctypes, ("Link",))
	about_people = {doctype for doctype in doctypes if doctype in people or links[doctype] & people}
	about_people |= {doctype for doctype in doctypes if links[doctype] & about_people}
	about_people |= {*SENSITIVE_DOCTYPES}
	tables = get_field_options([*about_people], table_fields)
	about_people |= {child for parent in about_people for child in tables[parent]} & {*doctypes}
	return sorted(about_people | get_frappe_people_doctypes())


def get_frappe_people_doctypes() -> set[str]:
	"""PEOPLE_DOCTYPES, and FLOW_DATA_DOCTYPES on a Frappe with Flow, with their child tables, such as
	Contact Email. It reads cached doctype definitions, not frappe.get_all, because the exposure panel
	calls it (tests/test_ai_hygiene.py)."""
	named = (*PEOPLE_DOCTYPES, *FLOW_DATA_DOCTYPES)
	doctypes = [doctype for doctype in named if frappe.db.exists("DocType", doctype)]
	meta = [frappe.get_meta(doctype) for doctype in doctypes]
	tables = (field.options for each in meta for field in each.get_table_fields(include_computed=True))
	return {*doctypes, *tables}


def get_field_options(doctypes: list[str], fieldtypes: tuple[str, ...]) -> defaultdict[str, set[str]]:
	"""The doctypes that each of *doctypes* names in its fields of *fieldtypes*, Custom Fields included."""
	fieldtype = ("in", fieldtypes)
	rows = frappe.get_all(
		"DocField",
		filters={"parent": ("in", doctypes), "fieldtype": fieldtype},
		fields=["parent", "options"],
	) + frappe.get_all(
		"Custom Field",
		filters={"dt": ("in", doctypes), "fieldtype": fieldtype},
		fields=["dt as parent", "options"],
	)
	options = defaultdict(set)
	for row in rows:
		options[row.parent].add(row.options)
	return options


def fill_blocked_knowledge_doctypes() -> None:
	"""after_install and a v1_0 patch: start an empty Blocked from Flow Knowledge with the recommended
	doctypes. A list with rows stays as it is, so it is safe to run again."""
	settings = frappe.get_single(SETTINGS)
	if not settings.blocked_knowledge_doctypes:
		add_recommended_knowledge_doctypes(settings)


def forget_missing_blocked_doctypes(app_name: str | None = None) -> None:
	"""after_migrate, and after_app_uninstall with the app's name: delete each Blocked from Flow
	Knowledge row whose doctype is gone. A migrate deletes the doctypes that a release removed, and an
	uninstall the app's doctypes, without checking links, and such a row fails every save of Church AI
	Settings, turning AI off included."""
	frappe.db.delete(
		"Church AI Blocked DocType", {"document_type": ("not in", frappe.get_all("DocType", pluck="name"))}
	)
	if app_name:
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (an uninstall commits before its hooks)


def add_recommended_knowledge_doctypes(settings) -> int:
	"""Add each recommended doctype that Blocked from Flow Knowledge lacks, keep every row, and return
	how many it added."""
	blocked = settings.blocked_doctypes
	missing = [doctype for doctype in get_recommended_knowledge_doctypes() if doctype not in blocked]
	for doctype in missing:
		settings.append("blocked_knowledge_doctypes", {"document_type": doctype})
	if missing:
		settings.save()
	return len(missing)


@frappe.whitelist(methods=["POST"])
def use_recommended_knowledge_doctypes() -> int:
	"""Add the recommended doctypes that Church AI Settings' Blocked from Flow Knowledge lacks. Changes data.

	For System Managers and Church Managers; it works while AI is off. It keeps every row, a row that
	an admin added included, and returns how many rows it added.
	"""
	frappe.only_for(("System Manager", "Church Manager"), message=True)
	return add_recommended_knowledge_doctypes(frappe.get_single(SETTINGS))
