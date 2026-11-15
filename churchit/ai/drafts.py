# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""AI drafts: an agent proposes a record, a person checks the filled form and saves it.

A draft lives in Redis for an hour under its user and a random token, and nothing reaches the
database before the person saves the form. Its key (DRAFT_KEY) is not under Frappe's "user:" prefix,
which a sign-in clears, and hooks.py keeps it through a full clear_cache (persistent_cache_keys). A
draft keeps only what the caller could type into that form: it drops unknown fields, fields the
caller cannot write, docstatus and the fields whose save sends a message (SENDING_FIELDS). public/js/ai_drafts.js fills the form from get_draft and calls
label_saved after the first save. Never rename get_draft or label_saved: browsers keep that script
for 12 hours.
"""

import frappe
from frappe import _
from frappe.model import display_fieldtypes, table_fields
from frappe.model.document import Document
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, get_datetime, get_url_to_form, now

from churchit.ai.switch import require_ai

DRAFT_SECONDS = 60 * 60
DRAFT_KEY = "churchit:ai_draft:"
SCALAR_TYPES = (str, int, float, bool, type(None))
# Fields whose save sends a message, found in each controller.
SENDING_FIELDS = {
	# ChurchEmail.send moves the status, and Send At moves a scheduled message.
	"Church Email": ("status", "send_after"),
	# MinistryTeamAssignment.on_update emails the team coordinator when the status becomes Declined.
	"Ministry Team Assignment": ("status",),
	# followup.start_cards opens cards on an active workflow, and its actions send email and texts.
	"Follow-up Workflow": ("is_active",),
}
# The value of a sending field that sends nothing, which a draft keeps: Active defaults to on.
QUIET_VALUES = {("Follow-up Workflow", "is_active"): 0}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60, user_based=True)
def propose(doctype: str, values: dict | str, name: str | None = None) -> dict:
	"""Draft a new record, or a change to one, and get the link that opens it unsaved in a form. Reads only.

	values maps fieldnames to values. A table field takes a list of rows: each row is added, or, when
	it has the name of a row of the record, changes that row. Give name to draft a change to that
	record. Nothing is saved: the person opens the url, checks each field and saves. dropped lists
	the fields left out because the caller cannot set them in the form, or because saving them would
	send or submit. Only the caller can open the draft, for one hour.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	frappe.has_permission(doctype, "write" if name else "create", doc=name, throw=True)
	return make_draft(doctype, frappe.parse_json(values), name)


def make_draft(doctype: str, values: dict, name: str | None = None, source: str | None = None) -> dict:
	"""What propose does, for churchit's own AI features and Flow tools, with the source of the draft
	(such as a Flow Model's name) for its label. It checks the switch and the caller's rights itself."""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	record = get_draft_target(doctype, name)
	name = None if record.is_new() else record.name
	if not isinstance(values, dict):
		frappe.throw(_("Give the values as an object of fieldnames and values."))

	dropped: list[str] = []
	kept = get_allowed_values(record, values, dropped)
	dropped += [fieldname for fieldname in values if fieldname not in kept]
	draft = {
		"doctype": doctype,
		"name": name,
		"values": kept,
		"source": source,
		"modified": None if record.is_new() else str(record.modified),
		"created": now(),
	}
	token = frappe.generate_hash(length=32)
	frappe.cache.set_value(get_key(token), draft, expires_in_sec=DRAFT_SECONDS)
	return {"url": f"{get_url_to_form(doctype, name or 'new')}?ai_draft={token}", "dropped": dropped}


def get_draft_target(doctype: str, name: str | None) -> Document:
	"""The record a draft changes, or a new one, once the caller may write it, or create one.

	A Single has one record, so its draft always changes that record.
	"""
	meta = frappe.get_meta(doctype)
	if meta.istable:
		frappe.throw(_("Draft the record that holds this table instead."))
	if meta.issingle:
		name = doctype
	if not name:
		frappe.has_permission(doctype, "create", throw=True)
		return frappe.new_doc(doctype)

	record = frappe.get_doc(doctype, name)
	record.check_permission("write")
	if record.docstatus == 2:
		frappe.throw(_("This record is cancelled, so it cannot change."))
	return record


def get_allowed_values(stored: Document, values: dict, dropped: list[str]) -> dict:
	"""The values the caller could type into the form of *stored*, in form order.

	*stored* is the record, one of its table rows or a new one. The rows of a table field drop their
	own fields into *dropped*.
	"""
	levels = stored.get_permlevel_access("write")
	kept: dict = {}
	for df in stored.meta.fields:
		value = values.get(df.fieldname)
		if df.fieldname not in values or not can_draft(stored, df, value, levels):
			continue
		if df.fieldtype not in table_fields:
			if isinstance(value, SCALAR_TYPES):
				kept[df.fieldname] = value
		elif isinstance(value, list) and frappe.db.exists("DocType", {"name": df.options, "istable": 1}):
			kept[df.fieldname] = get_allowed_rows(stored, df.fieldname, value, dropped)
	return kept


def can_draft(stored: Document, df, value, levels: list[int]) -> bool:
	"""True when the caller could set the field to *value* in the form and saving it sends nothing."""
	if df.fieldtype in display_fieldtypes or df.read_only or df.hidden or df.is_virtual:
		return False
	if df.permlevel not in levels or not is_quiet(stored.doctype, df.fieldname, value):
		return False
	if stored.docstatus == 1 and not df.allow_on_submit:
		return False
	return not (df.set_only_once and not stored.is_new() and stored.get(df.fieldname))


def is_quiet(doctype: str, fieldname: str, value) -> bool:
	"""False for a field whose save sends a message (SENDING_FIELDS), unless *value* sends nothing."""
	if fieldname not in SENDING_FIELDS.get(doctype, ()):
		return True
	key = (doctype, fieldname)
	return key in QUIET_VALUES and value == QUIET_VALUES[key]


def get_allowed_rows(record: Document, fieldname: str, rows: list, dropped: list[str]) -> list[dict]:
	"""The rows of one table field. A row keeps its name only when it names a row of the record."""
	stored_rows = {row.name: row for row in record.get(fieldname)}
	kept = []
	for row in rows:
		if not isinstance(row, dict):
			dropped.append(fieldname)
			continue
		stored = stored_rows.get(row.get("name")) or frappe.new_doc(
			record.meta.get_field(fieldname).options, parent_doc=record, parentfield=fieldname
		)
		values = get_allowed_values(stored, row, dropped)
		if not stored.is_new():
			values["name"] = stored.name
		dropped += [f"{fieldname}.{key}" for key in row if key not in values]
		kept.append(values)
	return kept


@frappe.whitelist(methods=["GET"])
def get_draft(token: str) -> dict:
	"""The caller's AI draft, to fill the form its link opens: doctype, name, values and stale. Reads only.

	stale is true when the record changed after the draft was made. Only the user the draft was made
	for gets it.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	draft = get_saved_draft(token)
	if not draft:
		frappe.throw(
			_("Draft not found. A draft lasts one hour, and only the person it was made for can open it."),
			frappe.DoesNotExistError,
		)

	is_stale = False
	if draft["name"]:
		record = frappe.get_doc(draft["doctype"], draft["name"])
		record.check_permission("read")
		is_stale = str(record.modified) != draft["modified"]
	return {"doctype": draft["doctype"], "name": draft["name"], "values": draft["values"], "stale": is_stale}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=60 * 60, user_based=True)
def label_saved(doctype: str, name: str, token: str) -> bool:
	"""Note on the timeline of a record saved from an AI draft that AI helped draft it. Changes data.

	The form calls it after the first save of the draft. It adds the note once per draft, only when
	the token is the caller's draft of this record and the record was saved after the draft, and
	not on a doctype whose form has no timeline. True when it added the note.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	record = frappe.get_doc(doctype, name)
	record.check_permission("write")
	draft = get_saved_draft(token)
	if not draft or not is_saved_from(record, draft):
		return False

	frappe.cache.delete_value(get_key(token))
	if record.meta.hide_toolbar:
		return False
	source = escape_html(draft["source"] or _("an AI app"))
	record.add_comment("Info", _("Drafted with AI help ({0}).").format(source))
	return True


def is_saved_from(record: Document, draft: dict) -> bool:
	"""True when *record* is the draft's record, saved after the draft was made."""
	if record.doctype != draft["doctype"]:
		return False
	if draft["name"]:
		return record.name == draft["name"] and str(record.modified) != draft["modified"]
	return record.owner == frappe.session.user and get_datetime(record.creation) >= get_datetime(
		draft["created"]
	)


def get_key(token: str) -> str:
	return f"{DRAFT_KEY}{frappe.session.user}:{token}"


def get_saved_draft(token: str) -> dict | None:
	"""The caller's draft. A token is 32 letters and digits, so a forged one cannot reach another key."""
	if not (isinstance(token, str) and len(token) == 32 and token.isalnum()):
		return None
	return frappe.cache.get_value(get_key(token), expires=True)
