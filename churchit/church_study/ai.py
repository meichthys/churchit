# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Sermon study helpers: questions, summaries, handout blanks and posts from a sermon's notes.

The AI never writes a sermon or a prayer. A published sermon's notes are on its public page, so a
devotional and a post read only them and need no privacy label. The other helpers also read a draft's
notes and the transcript, which is never published: those are church records, so the model needs a
label that allows them and the read leaves an Access Log row. Bible references and verse text follow
churchit.ai.writing, and handout blanks are only words to bracket, so make_handout makes the blanks.
"""

from typing import NamedTuple

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.core.utils import html_to_plain_text
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.rate_limiter import rate_limit
from frappe.utils import cstr, strip_html_tags

from churchit.ai import runner, writing
from churchit.ai.switch import require_ai

FEATURE = "Sermon study"
ACCESS_LOG_METHOD = "AI: Sermon study"
QUESTIONS, SUMMARY, SERIES_DESCRIPTION = "questions", "summary", "series_description"
HANDOUT_BLANKS, DEVOTIONAL, SOCIAL_POST = "handout_blanks", "devotional", "social_post"
# The Sermon fields a prompt holds. transcript is never published; the others are once the sermon is.
SERMON_FIELDS = ("title", "scripture", "sermon_date", "notes", "transcript")
PUBLIC_FIELDS = ("title", "scripture", "sermon_date", "notes")
# Read from the sermon's series: its name, and the titles and scripture of its published sermons.
SERIES_FIELDS = ("series_name",)
NOTES_LENGTH = 12000
TRANSCRIPT_LENGTH = 24000
MAX_QUESTIONS = 12
MAX_BLANKS = 15
BLANK_WORDS = 6
CHECK_TEXT = writing.CHECKS[writing.TEXT]


class Helper(NamedTuple):
	"""One study helper: what the model writes, the answer's JSON form, its check and what it reads."""

	instruction: str
	answer: str
	check: str
	fields: tuple[str, ...] = SERMON_FIELDS
	# Only for a sermon that guests can open, from its public fields.
	published_only: bool = False


HELPERS = {
	QUESTIONS: Helper(
		"Write 5 to 8 questions that help a small group talk about this sermon and live it out. Start "
		"with an easy question.",
		'{"questions": ["..."], "references": ["..."]}',
		"churchit.church_study.ai.check_questions",
	),
	SUMMARY: Helper("Summarize the sermon in exactly 3 sentences.", writing.TEXT_ANSWER, CHECK_TEXT),
	SERIES_DESCRIPTION: Helper(
		"Write a short public description, of 2 to 4 sentences, of the sermon series that this sermon "
		"belongs to. It invites people to come.",
		writing.TEXT_ANSWER,
		CHECK_TEXT,
	),
	HANDOUT_BLANKS: Helper(
		"Choose 5 to 12 key words or short phrases of the notes for listeners to fill in on a handout. "
		f"Copy each exactly as the notes write it, at most {BLANK_WORDS} words, in the order of the notes.",
		'{"blanks": ["..."]}',
		"churchit.church_study.ai.check_blanks",
		fields=("title", "scripture", "notes"),
	),
	DEVOTIONAL: Helper(
		"Write a short devotional of about 200 words for the week after this sermon, from its notes.",
		writing.TEXT_ANSWER,
		CHECK_TEXT,
		fields=PUBLIC_FIELDS,
		published_only=True,
	),
	SOCIAL_POST: Helper(
		"Write a social media post of at most 280 characters that invites people to watch or listen to "
		"this sermon.",
		writing.TEXT_ANSWER,
		CHECK_TEXT,
		fields=PUBLIC_FIELDS,
		published_only=True,
	),
}
STUDY_RULES = (
	"You help a church's staff make study material from a sermon.",
	"Where Christian traditions differ, present the main views fairly. Add no teaching that the sermon "
	"does not give.",
	*writing.RULES,
)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60, user_based=True)
def study_helper(sermon: str, purpose: str) -> dict:
	"""Start an AI study helper for a sermon: discussion questions, a summary, a series description, handout blanks, or for a published sermon a devotional or a social post. Changes data.

	purpose is questions, summary, series_description, handout_blanks, devotional or social_post. It
	never writes a sermon or a prayer. The answer reaches the caller's browser as a suggestion, and
	nothing is saved. It starts a model run, which Flow keeps as a chat of the caller. Returns {"token"}.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	helper = HELPERS.get(purpose)
	if not helper:
		frappe.throw(_("Churchit's AI writes study helpers for a sermon, never a sermon or a prayer."))
	doc = frappe.get_doc("Sermon", sermon)
	doc.check_permission("read")
	is_public = doc.is_public
	if helper.published_only and not is_public:
		frappe.throw(_("A devotional and a social post are drafted only for a published sermon."))

	doc.apply_fieldlevel_read_permissions()
	values = get_sermon_values(doc, helper.fields)
	refuse_missing_text(purpose, doc, values)

	has_records = not is_public or "transcript" in values
	if has_records:
		make_access_log(doctype="Sermon", document=doc.name, method=ACCESS_LOG_METHOD)
	return runner.start(
		FEATURE,
		get_study_prompt(helper, doc, values, purpose == SERIES_DESCRIPTION),
		sends=("Sermon",) if has_records else (),
		reference_doctype="Sermon",
		reference_name=doc.name,
		check=helper.check,
	)


def refuse_missing_text(purpose: str, doc, values: dict) -> None:
	"""Refuse a helper whose sermon lacks what it reads."""
	if not (values.get("notes") or values.get("transcript")):
		frappe.throw(_("Add notes or a transcript to the sermon first."))
	if purpose == HANDOUT_BLANKS and not values.get("notes"):
		frappe.throw(_("Add notes to the sermon first: the handout blanks come from its notes."))
	if purpose == SERIES_DESCRIPTION and not doc.series:
		frappe.throw(_("Choose the sermon's series first."))


def get_sermon_values(doc, fields: tuple[str, ...]) -> dict:
	"""The *fields* of the sermon that hold a value and that the caller may read, as plain text."""
	masked = doc.flags.masked_fieldnames or set()
	values = {}
	for fieldname in fields:
		value = doc.get(fieldname)
		if not value or fieldname in masked:
			continue
		if fieldname == "notes":
			value = html_to_plain_text(value)[:NOTES_LENGTH]
		elif fieldname == "transcript":
			value = cstr(value)[:TRANSCRIPT_LENGTH]
		values[fieldname] = value
	return values


def get_study_prompt(helper: Helper, doc, values: dict, with_series: bool) -> str:
	"""The rules and the answer's form, then the sermon as a data block."""
	lines = [
		f"{_(doc.meta.get_label(fieldname))}: {frappe.format(value, 'Date') if fieldname == 'sermon_date' else value}"
		for fieldname, value in values.items()
	]
	if with_series:
		lines += get_series_lines(doc.series)
	instructions = "\n".join(
		[*STUDY_RULES, helper.instruction, f"Answer with JSON only, in this form: {helper.answer}"]
	)
	return "\n\n".join((instructions, runner.wrap_data("\n".join(lines), "sermon")))


def get_series_lines(series: str) -> list[str]:
	names = writing.get_readable_list("Sermon Series", filters={"name": series}, pluck=SERIES_FIELDS[0])
	sermons = writing.get_series_sermons(series)
	return [
		*([f"{_('Series')}: {names[0]}"] if names else []),
		*([f"{_('Published sermons of the series')}: {sermons}"] if sermons else []),
	]


# Checks: the runner calls one with the parsed answer, as the caller, before the browser sees it.


def check_questions(answer) -> dict:
	"""The questions, without each one that names a passage scripture cannot read."""
	questions = answer.get("questions") if isinstance(answer, dict) else None
	if not isinstance(questions, list):
		writing.refuse_answer()
	kept, dropped = [], []
	for question in questions[:MAX_QUESTIONS]:
		text = " ".join(strip_html_tags(question).split()) if isinstance(question, str) else ""
		unreadable = writing.get_unreadable(text)
		dropped += unreadable
		if text and not unreadable:
			kept.append(text)
	if not kept:
		writing.refuse_answer()

	listed = writing.get_listed_references(answer)
	found = [reference for question in kept for reference in writing.find_references(question)]
	return {"questions": kept, "references": writing.get_passages([*listed, *found]), "dropped": dropped}


def check_blanks(answer) -> dict:
	"""Short phrases to bracket in the notes, each once, without brackets or markup of their own."""
	blanks = answer.get("blanks") if isinstance(answer, dict) else None
	if not isinstance(blanks, list):
		writing.refuse_answer()
	kept = {}
	for blank in blanks:
		if not isinstance(blank, str):
			continue
		text = " ".join(strip_html_tags(blank).replace("[", " ").replace("]", " ").split())
		if text and len(text.split()) <= BLANK_WORDS:
			kept.setdefault(text.casefold(), text)
	if not kept:
		writing.refuse_answer()
	return {"blanks": list(kept.values())[:MAX_BLANKS]}
