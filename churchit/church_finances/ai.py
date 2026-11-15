# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Suggest Type on an Expense: churchit's AI picks one of the church's Expense Types (churchit.ai.runner).

The prompt holds the expense's notes, the vendor's name when the vendor is ticked Is a Business, and the names
of the Expense Types that the expense's church may use; never an amount, an account, a fund, bank or
payee details, the title (it can hold a person's name) or a person's name. The check keeps the answer
only when it is one of those types, and the form fills it unsaved.
"""

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.rate_limiter import rate_limit

from churchit.ai import opt_outs, runner
from churchit.ai.switch import require_ai
from churchit.church_people.ai_actions import HOUR, RUNS_AN_HOUR
from churchit.church_scope import allowed_churches, default_church, document_church, is_multi_church

EXPENSE_TYPE_SUGGESTION = "Expense type suggestion"
ROLES = ("Church Finance", "Church Manager")
# The Expense fields that Suggest Type reads; only notes and the vendor's name reach the prompt.
EXPENSE_FIELDS = ("church", "vendor", "notes", "missionary")
MAX_NOTES = 1000
MAX_TYPES = 300
NO_MATCH = "AI did not find a matching expense type."
INSTRUCTIONS = """Choose the expense type of a church expense from the vendor and the notes in the data block.
Answer with one JSON object and nothing else. Shape: {{"church": "{church}", "type": "<expense type>"}}.
Use one of these expense types, written as listed, or "" when none fits: {types}"""


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=RUNS_AN_HOUR, seconds=HOUR, user_based=True)
def suggest_expense_type(expense: str | dict) -> dict:
	"""Start an AI run that suggests the Expense Type of an Expense from its vendor and notes. Changes data.

	*expense* is a draft Expense you may edit, or the church, vendor and notes of a new one. For Church
	Finance and Church Manager. The prompt holds the notes, the vendor's name when the vendor is ticked
	Is a Business, and the church's Expense Types; never amounts, funds, accounts or payee details. The answer
	comes to your browser as one of the church's Expense Types; nothing is saved.
	"""
	require_ai()
	frappe.only_for(ROLES, message=True)
	doc = get_expense(expense)
	if doc.missionary:
		frappe.throw(_("A missionary's expense takes its type from the Missionary."))
	church = document_church(doc) or default_church()
	opt_outs.refuse_kept_away_church(church)
	types = get_expense_types(church)
	if not types:
		frappe.throw(_("Add an Expense Type with a fund your church may use first."))

	vendor = get_vendor_name(doc.vendor)
	notes = (doc.notes or "").strip()[:MAX_NOTES]
	if not (vendor or notes):
		frappe.throw(_("Choose a vendor that is a business, or write notes first."))

	if not doc.is_new():
		make_access_log(doctype="Expense", document=doc.name, method=f"AI: {EXPENSE_TYPE_SUGGESTION}")
	data = "\n".join(f"{label}: {value}" for label, value in (("Vendor", vendor), ("Notes", notes)) if value)
	instructions = INSTRUCTIONS.format(church=church or "", types=", ".join(types))
	return runner.start(
		EXPENSE_TYPE_SUGGESTION,
		f"{instructions}\n\n{runner.wrap_data(data, 'expense')}",
		sends=("Expense",),
		reference_doctype=None if doc.is_new() else "Expense",
		reference_name=None if doc.is_new() else doc.name,
		check="churchit.church_finances.ai.check_expense_type",
	)


def get_expense(expense: str | dict):
	"""The draft Expense named *expense* that the caller may edit, or an unsaved one of the values
	*expense* gives (EXPENSE_FIELDS only) that the caller may create."""
	values = frappe.parse_json(expense) if isinstance(expense, str) and expense.startswith("{") else expense
	if isinstance(values, dict):
		doc = frappe.get_doc({"doctype": "Expense", **{field: values.get(field) for field in EXPENSE_FIELDS}})
		doc.check_permission("create")
		return doc
	doc = frappe.get_doc("Expense", values)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("Suggest Type works on a draft expense."))
	opt_outs.refuse_kept_away("Expense", doc.name)
	return doc


def get_expense_types(church: str | None) -> list[str]:
	"""The Expense Types (not groups) the caller may read whose fund *church* may use: its own or a
	shared one, as Expense.validate allows (church_scope.refuse_another_churches_record)."""
	types = frappe.get_list(
		"Expense Type",
		filters={"is_group": 0, "fund": ("is", "set")},
		fields=["name", "fund"],
		order_by="name asc",
		limit=MAX_TYPES,
	)
	if not is_multi_church():
		return [row.name for row in types]
	funds = frappe.get_list(
		"Fund", filters={"name": ("in", list({row.fund for row in types}))}, fields=["name", "church"]
	)
	usable = {fund.name for fund in funds if not fund.church or fund.church == church}
	return [row.name for row in types if row.fund in usable]


def get_vendor_name(vendor: str | None) -> str | None:
	"""The name of *vendor* when the caller may read it and it is ticked Is a Business, else None.

	A vendor whose name is a Person's full name or whose email is a Person's email counts as a person
	even when ticked. That is read with frappe.db and not as the caller, because a finance user may not
	read the directory, and what churchit's AI sends must not depend on that.
	"""
	if not vendor or not frappe.has_permission("Vendor", doc=vendor):
		return None
	name, email, is_business = frappe.db.get_value("Vendor", vendor, ["vendor_name", "email", "is_business"])
	if not is_business:
		return None
	is_person = frappe.db.exists("Person", {"full_name": name}) or (
		email and frappe.db.exists("Email Address", {"parenttype": "Person", "email_address": email})
	)
	return None if is_person else name


def check_expense_type(answer: dict) -> dict:
	"""The runner's check for suggest_expense_type: {"church", "type"}, one of the Expense Types of the
	answer's church, a church the caller may read; else NO_MATCH. The form refuses another church."""
	if not isinstance(answer, dict):
		frappe.throw(_(runner.UNUSABLE))
	church = answer.get("church") or None
	if church is not None and not isinstance(church, str):
		frappe.throw(_(runner.UNUSABLE))
	readable = allowed_churches()
	if is_multi_church() and readable is not None and church not in readable:
		frappe.throw(_("The AI answered for another church."))
	expense_type = answer.get("type")
	if not isinstance(expense_type, str) or expense_type not in get_expense_types(church):
		frappe.throw(_(NO_MATCH))
	return {"church": church, "type": expense_type}
