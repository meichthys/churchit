# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Suggestions on new requests: a reviewer's AI run reads a new prayer request, care request or
follow-up card from a connection card or a form and suggests next steps. It never replies, publishes,
sends or changes the request.

dispatch (after_insert) only checks the gates and queues run_triage after the commit, so nothing goes
to a model inside the request that made the record, often a guest's web form. run_triage runs as the
church's reviewer (Church AI Settings, Reviewers, reviewer_for), checks every gate again, builds the
prompt from the saved record (what guests and members wrote only inside runner.wrap_data) and starts
the run through the runner with store as the Flow Run's on_complete, which Flow calls as the reviewer
when the run ends. A prayer or care request keeps its suggestion in a Church AI Suggestion, which only
Church Pastoral Care, Church Manager and System Manager read. When a prayer request is flagged with a
possible risk of harm, its suggestion (not the request) is assigned at once to the Pastoral Care users
of its church, so no other reader of the request sees the assignment. A follow-up card gets an "AI
suggestion" Comment (SUGGESTION), and its Draft the Email button opens the suggested email as an
unsaved Church Email (draft_email). No suggestion changes a request's own fields, its status, its
visibility or who it is assigned to, and none sends anything.
"""

import json
import re
from urllib.parse import urlparse

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.core.doctype.comment.comment import get_document_comments
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, get_url
from frappe.utils.user import get_users_with_role

from churchit.ai import runner
from churchit.ai.drafts import make_draft
from churchit.ai.flow_models import is_flow_ready
from churchit.ai.opt_outs import is_kept_away
from churchit.ai.switch import SETTINGS, get_setting, has_flow, is_ai_on, require_ai
from churchit.ai.writing import check_message, check_text
from churchit.church_people.ai_actions import JSON_ONLY, to_paragraphs
from churchit.church_people.followup import CARD, WORKFLOW
from churchit.church_prayers.prayer_access import PRAYER_REQUEST, PRIVATE
from churchit.church_scope import church_filters, is_multi_church
from churchit.church_setup.doctype.church_ai_suggestion.church_ai_suggestion import (
	SUGGESTION_DOCTYPE,
	set_suggestion,
)

CARE_REQUEST = "Care Request"
CONNECTION_CARD = "Connection Card"
FORM_RESPONSE = "Form Response"
CARD_SOURCES = (CONNECTION_CARD, FORM_RESPONSE)
FEATURES = {
	PRAYER_REQUEST: "Prayer request suggestions",
	CARE_REQUEST: "Care request suggestions",
	CARD: "Follow-up suggestions",
}
JOB = "churchit.ai.triage.run_triage"
STORE = "churchit.ai.triage.store"
PASTORAL_CARE = "Church Pastoral Care"
PRAYER_TYPE = "Prayer Request Type"
CARE_TYPE = "Care Request Type"
# The doctypes whose names a suggestion may name; the reviewer must select them.
CHOICE_DOCTYPES = (PRAYER_TYPE, CARE_TYPE, WORKFLOW)
# The subject of the Comment that holds a follow-up card's suggestion; anonymizing a person deletes them.
SUGGESTION = "AI suggestion"
# A prayer request's flags, by the code the model answers with.
FLAGS = {
	"risk": "Possible risk of harm",
	"others": "Names someone else",
	"health": "Health details",
	"contact": "Contact details",
	"spam": "Possible spam",
}
RISK = "risk"
UNCLEAR = "unclear"
NEEDS_A_PERSON = "Needs a person"
# The assignment of a flagged prayer request's suggestion; its notice and email give no reason.
RISK_ASSIGNMENT = "Read this prayer request now."
NO_EMAIL = "This card has no email that AI drafted."
MAX_CHOICES = 100
MAX_LINE = 300
MAX_WORDING = 500
MAX_SUBJECT = 140
DRAFTS_AN_HOUR = 30
# A web address in a model's answer; one that does not point to this site is removed.
LINK = re.compile(r"\b(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)

PRAYER_INSTRUCTIONS = """Read the prayer request in the data block and suggest how the church's pastoral care team should handle it. Never write a reply or a prayer.
{json_only} Shape: {{"type": "...", "urgent": true or false, "flags": ["..."], "public_wording": "..."}}.
type is one of: {types}. flags lists each code that applies: "risk" (someone may harm themselves or others, or is in danger), "others" (it names a person other than the one who asks), "health" (it gives health details), "contact" (it gives a phone number, an email or an address) and "spam" (it is not a prayer request). When you are not sure about a code, add "unclear". public_wording says what to pray for in at most two sentences that the whole church may read, with no names, health details or contact details."""

CARE_INSTRUCTIONS = """Read the care request in the data block and suggest its category and urgency for the church's care team. Never write a reply.
{json_only} Shape: {{"type": "...", "urgency": "..."}}.
type is one of: {types}. urgency is one of: {urgencies}."""

CARD_INSTRUCTIONS = """A person sent the church the {source} in the data block, and a follow-up card opened for them on the workflow {workflow}. Suggest the follow-up workflow that fits them best, why, and a first email from the church to them.
{json_only} Shape: {{"workflow": "...", "reason": "...", "email_subject": "...", "email": "..."}}.
workflow is one of the workflows below. reason is one sentence. The email is short, warm plain text that greets them with {{{{ first_name }}}}; use no other placeholder, no link and no promise that the workflows do not make.
Workflows:
{workflows}"""


def dispatch(doc: Document, method=None) -> None:
	"""after_insert of Prayer Request, Care Request and Follow-up Card: queue run_triage after the commit
	when every gate allows it. Nothing goes to a model here. An imported record (Data Import, sample
	data) is history, not a new request, so it gets no suggestion."""
	if frappe.flags.in_import or not get_reviewer(doc):
		return
	frappe.enqueue(
		JOB,
		queue="long",
		enqueue_after_commit=True,
		job_id=f"ai-triage:{doc.doctype}:{doc.name}",
		deduplicate=True,
		doctype=doc.doctype,
		name=doc.name,
	)


def run_triage(doctype: str, name: str) -> None:
	"""Long-queue job: as the church's reviewer, check every gate again and start the suggestion run."""
	if doctype not in FEATURES or not frappe.db.exists(doctype, name):
		return
	doc = frappe.get_doc(doctype, name)
	reviewer = get_reviewer(doc)
	if not reviewer:
		return

	user = frappe.session.user
	frappe.set_user(reviewer)
	try:
		start_run(doc)
	finally:
		frappe.set_user(user)


def get_reviewer(doc: Document) -> str | None:
	"""The reviewer whose run suggests on *doc*, or None when a gate refuses.

	The gates: AI and suggestions are on and Flow is ready; the record is one that gets suggestions;
	its church has a reviewer; neither its church nor its person keeps away from AI; the reviewer reads
	the record and the agent; the agent's model has a label the record allows.
	"""
	if not (is_on() and has_flow() and is_flow_ready() and is_suggested(doc)):
		return None
	reviewer = reviewer_for(doc.get("church"))
	if not reviewer or is_kept_away(doc.doctype, doc.name):
		return None
	return reviewer if can_read(doc, reviewer) and can_run(doc, reviewer) else None


def is_on() -> bool:
	"""True while AI and Suggest Next Steps on New Requests are on."""
	return is_ai_on() and bool(get_setting(SETTINGS, "suggest_request_triage"))


def is_suggested(doc: Document) -> bool:
	"""Never a Private prayer request, and a follow-up card only from a connection card or a form."""
	if doc.doctype == PRAYER_REQUEST:
		return doc.visibility != PRIVATE
	if doc.doctype == CARD:
		return doc.source_type in CARD_SOURCES
	return doc.doctype == CARE_REQUEST


def reviewer_for(church: str | None) -> str | None:
	"""The reviewer of *church*'s new requests: an enabled desk user, or None.

	On a site with several churches only the row that names the church counts. On a site with one
	church the first row counts, with or without a church.
	"""
	rows = frappe.get_cached_doc(SETTINGS).get("triage_reviewers") or []
	if is_multi_church():
		rows = [row for row in rows if church and row.church == church]
	user = rows[0].user if rows else None
	return user if user and is_desk_user(user) else None


def is_desk_user(user: str) -> bool:
	login = frappe.db.get_value("User", user, ["enabled", "user_type"], as_dict=True)
	return bool(login and login.enabled and login.user_type == "System User")


def can_read(doc: Document, user: str) -> bool:
	"""True when *user* reads the record and, for a card from a connection card, that card too."""
	if not frappe.has_permission(doc.doctype, "read", doc=doc, user=user):
		return False
	if doc.doctype == CARD and doc.source_type == CONNECTION_CARD:
		return frappe.has_permission(CONNECTION_CARD, "read", doc=doc.source_name, user=user)
	return True


def can_run(doc: Document, user: str) -> bool:
	"""True when *user* may use the agent for *doc* and its model's label allows the record."""
	agent = runner.get_agent(set(get_sends(doc)))
	if not frappe.has_permission("Flow Agent", "read", doc=runner.get_agent_name(agent), user=user):
		return False
	try:
		runner.check_label(FEATURES[doc.doctype], agent, has_records=True)
	except frappe.PermissionError:
		# dispatch runs in the request that made the record, often a guest's web form.
		frappe.clear_last_message()
		return False
	return True


def get_sends(doc: Document) -> tuple[str, ...]:
	if doc.doctype == CARD and doc.source_type == CONNECTION_CARD:
		return (CARD, CONNECTION_CARD)
	return (doc.doctype,)


def start_run(doc: Document) -> None:
	"""Start the suggestion run on *doc* as the reviewer, with one Access Log row for each record sent."""
	doc.apply_fieldlevel_read_permissions()
	prompt = get_prompt(doc)
	feature = FEATURES[doc.doctype]
	make_access_log(doctype=doc.doctype, document=doc.name, method=f"AI: {feature}")
	if CONNECTION_CARD in get_sends(doc):
		make_access_log(doctype=CONNECTION_CARD, document=doc.source_name, method=f"AI: {feature}")
	runner.start(
		feature,
		prompt,
		sends=get_sends(doc),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		deliver=STORE,
	)


def get_prompt(doc: Document) -> str:
	if doc.doctype == PRAYER_REQUEST:
		return get_prayer_prompt(doc)
	if doc.doctype == CARE_REQUEST:
		return get_care_prompt(doc)
	return get_card_prompt(doc)


def get_prayer_prompt(doc: Document) -> str:
	instructions = PRAYER_INSTRUCTIONS.format(json_only=JSON_ONLY, types=json.dumps(get_choices(PRAYER_TYPE)))
	sent = {"title": doc.title, "request": doc.request}
	return f"{instructions}\n\n{wrap(sent, doc, 'prayer request')}"


def get_care_prompt(doc: Document) -> str:
	instructions = CARE_INSTRUCTIONS.format(
		json_only=JSON_ONLY,
		types=json.dumps(get_choices(CARE_TYPE)),
		urgencies=json.dumps(get_options(CARE_REQUEST, "urgency")),
	)
	sent = {field: doc.get(field) for field in ("category", "urgency", "preferred_contact", "description")}
	return f"{instructions}\n\n{wrap(sent, doc, 'care request')}"


def get_card_prompt(doc: Document) -> str:
	"""The card's reason and, from a connection card, what the guest ticked and wrote. A form's answers
	stay out: the card's readers do not all read Form Responses."""
	workflows = frappe.get_list(
		WORKFLOW,
		filters=church_filters(doc.church, is_active=1),
		fields=["name", "description"],
		order_by="name asc",
		limit=MAX_CHOICES,
	)
	instructions = CARD_INSTRUCTIONS.format(
		source=doc.source_type.lower(),
		workflow=json.dumps(doc.workflow),
		json_only=JSON_ONLY,
		workflows="\n".join(f"- {json.dumps(row.name)}: {get_line(row.description)}" for row in workflows),
	)
	sent = {"reason": doc.reason}
	if doc.source_type == CONNECTION_CARD:
		source = frappe.get_doc(CONNECTION_CARD, doc.source_name)
		source.check_permission("read")
		sent.update({field: source.get(field) for field in ("visit", "how_heard", "message")})
		sent["interests"] = [row.interest for row in source.interests]
	return f"{instructions}\n\n{wrap(sent, doc, doc.source_type.lower())}"


def wrap(sent: dict, doc: Document, what: str) -> str:
	"""*sent* as a data block that says whether a guest wrote it."""
	author = "a guest" if doc.owner == "Guest" else "a member or staff"
	return runner.wrap_data(json.dumps(sent, default=str, indent=1), f"{what} written by {author}")


def store(run) -> None:
	"""The suggestion run's on_complete, which Flow calls as the run's owner when the run ends: keep the
	suggestion when every gate still allows it. An answer that cannot be used counts as None."""
	doctype, name = run.reference_doctype, run.reference_name
	if doctype not in FEATURES or not is_on() or not frappe.db.exists(doctype, name):
		return
	doc = frappe.get_doc(doctype, name)
	if not can_store(doc):
		return
	try:
		answer = runner.get_result(run, None)
	except frappe.ValidationError:
		answer = None
	if doctype == PRAYER_REQUEST:
		store_prayer(doc, answer)
	elif doctype == CARE_REQUEST:
		store_care(doc, answer)
	else:
		store_card(doc, answer)


def can_store(doc: Document) -> bool:
	"""True when the run's owner is still the reviewer who reads the record, and neither a Private
	visibility nor an opt-out came after the run started."""
	if frappe.session.user != reviewer_for(doc.get("church")):
		return False
	return is_suggested(doc) and not is_kept_away(doc.doctype, doc.name) and doc.has_permission("read")


def store_prayer(doc: Document, answer) -> None:
	"""Keep the suggestion; a risk flag assigns it to the Pastoral Care users of the request's church."""
	values, codes = get_prayer_suggestion(answer)
	suggestion = set_suggestion(doc.doctype, doc.name, values)
	if RISK in codes:
		assign_to_pastoral_care(doc, suggestion)


def get_prayer_suggestion(answer) -> tuple[dict, set[str]]:
	"""The suggestion fields and the flag codes. An unclear answer, or part of one, needs a person."""
	answer = answer if isinstance(answer, dict) else {}
	codes = get_flag_codes(answer.get("flags"))
	suggested_type = answer.get("type")
	if suggested_type not in get_choices(PRAYER_TYPE):
		suggested_type = None
	urgent = answer.get("urgent")
	if suggested_type is None or not isinstance(urgent, bool):
		codes.add(UNCLEAR)

	labels = [_(label) for code, label in FLAGS.items() if code in codes]
	if UNCLEAR in codes:
		labels.append(_(NEEDS_A_PERSON))
	values = {
		"suggested_type": suggested_type,
		"suggested_urgent": int(urgent is True),
		"suggested_flags": "\n".join(labels) or None,
		"public_wording": get_text(answer.get("public_wording"), MAX_WORDING),
	}
	return values, codes


def get_flag_codes(flags) -> set[str]:
	"""The flag codes of an answer, in any case. No list, or a code that FLAGS does not name, is unclear."""
	if not isinstance(flags, list):
		return {UNCLEAR}
	given = {flag.strip().lower() if isinstance(flag, str) else None for flag in flags}
	codes = given & {*FLAGS, UNCLEAR}
	return codes if codes == given else {*codes, UNCLEAR}


def assign_to_pastoral_care(doc: Document, suggestion: str) -> None:
	"""Assign the *suggestion* on *doc* to each Church Pastoral Care user who reads both; the assignment
	sends its own notice. The request gets no assignment: each of its readers would see it, and only a
	risk flag makes one."""
	record = frappe.get_doc(SUGGESTION_DOCTYPE, suggestion)
	users = [
		user
		for user in get_users_with_role(PASTORAL_CARE)
		if is_desk_user(user)
		and frappe.has_permission(doc.doctype, "read", doc=doc, user=user)
		and frappe.has_permission(SUGGESTION_DOCTYPE, "read", doc=record, user=user)
	]
	if users:
		assign_to.add(
			{
				"assign_to": users,
				"doctype": SUGGESTION_DOCTYPE,
				"name": suggestion,
				"description": _(RISK_ASSIGNMENT),
			}
		)


def store_care(doc: Document, answer) -> None:
	answer = answer if isinstance(answer, dict) else {}
	suggested_type = answer.get("type") if answer.get("type") in get_choices(CARE_TYPE) else None
	urgency = answer.get("urgency") if answer.get("urgency") in get_options(CARE_REQUEST, "urgency") else None
	if suggested_type or urgency:
		set_suggestion(
			doc.doctype, doc.name, {"suggested_type": suggested_type, "suggested_urgency": urgency}
		)


def store_card(doc: Document, answer) -> None:
	"""Add the suggestion as an "AI suggestion" Comment on the card, as text."""
	suggestion = get_card_suggestion(doc, answer if isinstance(answer, dict) else {})
	if not suggestion:
		return
	# As Document.add_comment does: only System Managers create Comments, and the reviewer reads the card.
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"subject": SUGGESTION,
			"reference_doctype": CARD,
			"reference_name": doc.name,
			"content": get_suggestion_html(suggestion),
		}
	).insert(ignore_permissions=True)


def get_card_suggestion(doc: Document, answer: dict) -> dict | None:
	"""A workflow of the card's church, a reason and an email that keeps only the person placeholders."""
	workflows = get_choices(WORKFLOW, **church_filters(doc.church, is_active=1))
	workflow = answer.get("workflow") if answer.get("workflow") in workflows else None
	reason = get_line(get_text(answer.get("reason"), MAX_LINE))
	message = get_text(answer.get("email"), check=check_message)
	subject = get_line(get_text(answer.get("email_subject"), MAX_SUBJECT, check=check_message))
	if not (workflow or reason or message):
		return None
	return {
		"workflow": workflow,
		"reason": reason,
		"subject": subject if message else None,
		"message": message,
	}


def get_suggestion_html(suggestion: dict) -> str:
	"""The Comment: a label and each part as escaped text, the email marked for draft_email."""
	parts = [
		f"<p><strong>{escape_html(_('AI suggestion'))}.</strong> "
		f"{escape_html(_('Check it before you use it. Nothing was sent.'))}</p>"
	]
	for label, value in ((_("Workflow"), suggestion["workflow"]), (_("Why"), suggestion["reason"])):
		if value:
			parts.append(f"<p><strong>{escape_html(label)}:</strong> {escape_html(value)}</p>")
	if suggestion["message"]:
		subject = escape_html(suggestion["subject"] or "")
		parts.append(
			f'<p><strong>{escape_html(_("Email subject"))}:</strong> <span data-ai-email="subject">{subject}</span></p>'
		)
		parts.append(f'<div data-ai-email="message">{to_paragraphs(suggestion["message"])}</div>')
	return "".join(parts)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=DRAFTS_AN_HOUR, seconds=60 * 60, user_based=True)
def draft_email(card: str) -> dict:
	"""Open the email that the AI suggestion on a follow-up card drafted, as an unsaved Church Email. Reads only.

	The email goes to the card's person only after you check it and send it from the Church Email
	form. Returns url, the unsaved form, and dropped, the fields you cannot set.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	record = frappe.get_doc(CARD, card)
	record.check_permission("read")
	email = get_suggested_email(record)
	if not email:
		frappe.throw(_(NO_EMAIL))
	values = {
		"channel": "Email",
		"church": record.church,
		"send_to": "Chosen People",
		"people": [{"person": record.person}],
		**email,
	}
	return make_draft("Church Email", values, source=_(SUGGESTION))


def get_suggested_email(card: Document) -> dict | None:
	"""The subject and message of the latest AI suggestion that the church's reviewer added to the card,
	or None. The caller reads the card."""
	rows = get_document_comments(
		CARD,
		card.name,
		fields=["content"],
		comment_types=["Comment"],
		extra_filters=[["subject", "=", SUGGESTION], ["owner", "=", reviewer_for(card.church) or ""]],
		order_by="creation desc",
		limit=1,
	)
	page = BeautifulSoup(rows[0].content or "", "html.parser") if rows else None
	message = page and page.find(attrs={"data-ai-email": "message"})
	if not message:
		return None
	subject = page.find(attrs={"data-ai-email": "subject"})
	return {"subject": subject.get_text() if subject else None, "message": message.decode_contents()}


def get_choices(doctype: str, **filters) -> list[str]:
	"""The names of *doctype* the reviewer may pick, the only values a suggestion may name."""
	if not frappe.has_permission(doctype, "select"):
		return []
	return frappe.get_list(doctype, filters=filters, pluck="name", order_by="name asc", limit=MAX_CHOICES)


def get_options(doctype: str, fieldname: str) -> list[str]:
	return [option for option in frappe.get_meta(doctype).get_options(fieldname).split("\n") if option]


def get_text(value, longest: int | None = None, check=check_text) -> str | None:
	"""A text part of the answer through *check*, without links to other sites, or None."""
	if not isinstance(value, str):
		return None
	try:
		text = check({"text": value})["text"]
	except frappe.ValidationError:
		frappe.clear_last_message()
		return None
	return remove_outside_links(text)[:longest] or None


def get_line(text: str | None) -> str | None:
	return " ".join((text or "").split())[:MAX_LINE] or None


def remove_outside_links(text: str) -> str:
	"""*text* with each web address that does not point to this site removed."""
	host = urlparse(get_url()).hostname

	def replace(match: re.Match) -> str:
		link = match.group(0)
		target = urlparse(link if "://" in link else f"https://{link}").hostname
		return link if target == host else _("[link removed]")

	return LINK.sub(replace, text)
