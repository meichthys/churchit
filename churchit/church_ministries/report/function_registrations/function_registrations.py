# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_scope import scoped
from churchit.questions import get_questions
from churchit.utils import set_report_link_titles

# A question's column, apart from the report's own columns whatever the question is called.
ANSWER_COLUMN = "answer_{}"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	questions = []
	if filters.function:
		frappe.has_permission("Function", doc=filters.function, throw=True)
		question_set = frappe.db.get_value("Function", filters.function, "question_set")
		questions = get_questions(question_set) if question_set else []

	columns = get_columns(questions)
	data = get_data(filters)
	if questions:
		add_answers(data)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(questions) -> list[dict]:
	"""The sign-up and attendee columns, then one column for each question of the function's Question Set."""
	return [
		{
			"fieldname": "sign_up",
			"fieldtype": "Link",
			"label": _("Sign-Up"),
			"options": "Function Sign-Up",
			"width": 220,
		},
		{
			"fieldname": "function",
			"fieldtype": "Link",
			"label": _("Function"),
			"options": "Function",
			"width": 180,
		},
		{"fieldname": "attendee_name", "fieldtype": "Data", "label": _("Attendee"), "width": 180},
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 160},
		{"fieldname": "selection", "fieldtype": "Data", "label": _("Selection"), "width": 120},
		{"fieldname": "status", "fieldtype": "Data", "label": _("Status"), "width": 100},
		{"fieldname": "amount_due", "fieldtype": "Currency", "label": _("Amount Due"), "width": 110},
		{"fieldname": "amount_paid", "fieldtype": "Currency", "label": _("Amount Paid"), "width": 110},
		{"fieldname": "payment_status", "fieldtype": "Data", "label": _("Payment Status"), "width": 120},
		*(
			{
				"fieldname": ANSWER_COLUMN.format(question.fieldname),
				"fieldtype": "Data",
				"label": question.label,
				"width": 160,
			}
			for question in questions
		),
	]


def get_data(filters) -> list[dict]:
	"""One row for each attendee of the sign-ups of the functions the reader may see."""
	SignUp = frappe.qb.DocType("Function Sign-Up")
	Attendee = frappe.qb.DocType("Function Sign-Up Attendee")
	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Attendee)
		.join(SignUp)
		.on((SignUp.name == Attendee.parent) & (Attendee.parenttype == "Function Sign-Up"))
		.join(Function)
		.on(Function.name == SignUp.function)
		.select(
			SignUp.name.as_("sign_up"),
			SignUp.function,
			Attendee.name.as_("attendee"),
			Attendee.attendee_name,
			Attendee.person,
			Attendee.selection,
			SignUp.status,
			SignUp.amount_due,
			SignUp.amount_paid,
			SignUp.payment_status,
		)
		.orderby(Function.start_date)
		.orderby(SignUp.creation)
		.orderby(Attendee.idx)
	)
	if filters.function:
		query = query.where(SignUp.function == filters.function)
	if filters.status:
		query = query.where(SignUp.status == filters.status)
	return scoped(query, Function, filters).run(as_dict=True)


def add_answers(data: list[dict]) -> None:
	"""Put each attendee's answers in the question columns."""
	if not data:
		return
	# church-scope: the answers of the attendee rows read above, which are scoped by their Function
	answers = frappe.get_all(
		"Question Answer",
		filters={"parenttype": "Function Sign-Up", "attendee": ("in", [row.attendee for row in data])},
		fields=["attendee", "question", "answer"],
	)
	by_attendee = {row.attendee: row for row in data}
	for answer in answers:
		by_attendee[answer.attendee][ANSWER_COLUMN.format(answer.question)] = answer.answer
