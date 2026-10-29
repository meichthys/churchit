# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The questions a church asks on a registration, a form or a room booking, and the answers people give.

A Question Set lists the questions. `get_fields` turns them into field definitions, which
`churchit.questions.render` (`public/js/questions.js`) shows with a `frappe.ui.FieldGroup` in a desk Dialog or
on a Web Form page. `set_answers` checks what came back with `validate_answers` and keeps it on the record the
questions were asked for, in a Question Answer table with each question as it was asked. A question has no
conditions: a church that asks some people other questions makes a second Question Set.

Answers are kept as text. A tick is kept as Yes or No, and a date as YYYY-MM-DD. A question left blank keeps
no row. A merge keeps the answers, because they stay on their record. Anonymizing a person clears the answers,
and the change history, of every record that names them in a field of its own (`clear_answers`). A record that
names the person only in a table row, such as one attendee of a group, keeps its answers, which are the
group's.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, getdate, validate_email_address, validate_phone_number

QUESTION_SET = "Question Set"
ANSWER_DOCTYPE = "Question Answer"
YES, NO = "Yes", "No"
# Question type -> (field type, field options) of the field that asks it.
FIELDS = {
	"Data": ("Data", None),
	"Small Text": ("Small Text", None),
	"Select": ("Select", None),
	"Check": ("Check", None),
	"Date": ("Date", None),
	"Int": ("Int", None),
	"Email": ("Data", "Email"),
	"Phone": ("Data", "Phone"),
}


def get_fieldname(text: str | None) -> str:
	"""*text* as an answer name: lower case, with each run of anything but letters and digits made one "_"."""
	return re.sub(r"\W+", "_", cstr(text).lower()).strip("_")


def get_choices(options: str | None) -> list[str]:
	"""The choices of a Select question, one on each line of *options*."""
	return [line.strip() for line in cstr(options).splitlines() if line.strip()]


def get_questions(question_set: str) -> list[Document]:
	"""The questions of *question_set*, in order. The caller checks that the reader may use it."""
	return frappe.get_cached_doc(QUESTION_SET, question_set).questions


def get_fields(question_set: str) -> list[dict]:
	"""The field definitions that ask the questions of *question_set*, for `churchit.questions.render`."""
	fields = []
	for question in get_questions(question_set):
		fieldtype, options = FIELDS[question.question_type]
		if question.question_type == "Select":
			# A blank first choice, so that nothing is chosen until the person chooses.
			options = "\n".join(["", *get_choices(question.options)])
		fields.append(
			{
				"fieldname": question.fieldname,
				"label": question.label,
				"fieldtype": fieldtype,
				"options": options,
				"reqd": question.is_required,
			}
		)
	return fields


def validate_answers(question_set: str, answers: dict) -> dict[str, str]:
	"""The answers to the questions of *question_set* as they are kept, by answer name, in question order.

	Refuses an answer to a question the set does not ask, a required question left blank, and an answer that
	does not fit its question.
	"""
	questions = get_questions(question_set)
	unknown = set(answers) - {question.fieldname for question in questions}
	if unknown:
		frappe.throw(
			_("These are not questions of this Question Set: {0}").format(", ".join(sorted(unknown)))
		)
	kept = {}
	for question in questions:
		answer = clean_answer(question, answers.get(question.fieldname))
		if not answer and question.is_required:
			frappe.throw(_("Please answer {0}.").format(frappe.bold(question.label)), frappe.MandatoryError)
		if answer:
			kept[question.fieldname] = answer
	return kept


def clean_answer(question: Document, value) -> str:
	"""*value* as the text kept for *question*, or an empty string for no answer."""
	text = cstr(value).strip()
	if question.question_type == "Check":
		# A required tick must be ticked, so an unticked one is no answer there.
		ticked = text.lower() in ("1", "true")
		return YES if ticked else ("" if question.is_required else NO)
	return check_answer(question, text) if text else ""


def check_answer(question: Document, text: str) -> str:
	"""The answer *text* as kept for *question*; refuses one that does not fit the question."""
	kind = question.question_type
	if kind == "Select" and text not in get_choices(question.options):
		frappe.throw(_("{0} is not a choice of {1}.").format(text, frappe.bold(question.label)))
	if kind == "Int" and not re.fullmatch(r"[+-]?\d+", text):
		frappe.throw(_("{0} needs a whole number.").format(frappe.bold(question.label)))
	if kind == "Email":
		validate_email_address(text, throw=True)
	if kind == "Phone":
		validate_phone_number(text, throw=True)
	return str(getdate(text)) if kind == "Date" else text


def set_answers(doc: Document, question_set: str, answers: dict, table: str = "answers") -> None:
	"""Replace the rows of *doc*'s Question Answer table *table* with *answers* to *question_set*.

	Each row keeps the question as it was asked, so a later change to the set does not change an old answer. The
	caller saves *doc*.
	"""
	kept = validate_answers(question_set, answers)
	labels = {question.fieldname: question.label for question in get_questions(question_set)}
	doc.set(
		table, [{"question": name, "label": labels[name], "answer": answer} for name, answer in kept.items()]
	)


def get_answer_tables(doctype: str) -> list[str]:
	"""The fields of *doctype* that hold a Question Answer table."""
	return [
		df.fieldname for df in frappe.get_meta(doctype).get_table_fields() if df.options == ANSWER_DOCTYPE
	]


def clear_answers(doc: Document) -> None:
	"""Delete every answer kept on the saved record *doc*, in the database and on *doc*, without saving *doc*.

	The change history of *doc* goes too, because it holds the old answers.
	"""
	for fieldname in get_answer_tables(doc.doctype):
		doc.set(fieldname, [])
	frappe.db.delete(ANSWER_DOCTYPE, {"parenttype": doc.doctype, "parent": doc.name})
	frappe.db.delete("Version", {"ref_doctype": doc.doctype, "docname": doc.name})
