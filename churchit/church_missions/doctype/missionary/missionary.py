# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, add_months, add_years, getdate, today

# Maps each Missionary Support Frequency to the function that advances a date by
# one period. Keyed off the frequency record names seeded in
# churchit.patches.after_install._create_missionary_support_frequencies.
FREQUENCY_STEP = {
	"Weekly": lambda d: add_days(d, 7),
	"Bi-Weekly": lambda d: add_days(d, 14),
	"Monthly": lambda d: add_months(d, 1),
	"Bi-Monthly": lambda d: add_months(d, 2),
	"Quarterly": lambda d: add_months(d, 3),
	"Yearly": lambda d: add_years(d, 1),
}

# Safety cap so a misconfigured start date can never spin forever.
MAX_EXPENSES_PER_RUN = 1000


class Missionary(Document):
	def validate(self):
		if self.auto_create_expenses:
			if not self.support_amount or self.support_amount <= 0:
				frappe.throw(
					"A positive Support Amount is required to auto-create expenses."
				)
			if self.support_frequency not in FREQUENCY_STEP:
				frappe.throw(
					f"Support Frequency '{self.support_frequency}' is not supported for "
					"auto-creating expenses."
				)


def create_missionary_expenses():
	"""Daily scheduler: for every Missionary with auto_create_expenses enabled,
	create a draft Expense for each support period that has come due."""
	missionaries = frappe.get_all(
		"Missionary",
		filters={"auto_create_expenses": 1},
		fields=["name"],
	)
	for missionary in missionaries:
		try:
			_create_due_expenses(missionary.name)
		except Exception:
			frappe.log_error(
				title=f"Auto-create Missionary Expense failed for {missionary.name}",
				message=frappe.get_traceback(),
			)


def _create_due_expenses(missionary_name):
	missionary = frappe.get_doc("Missionary", missionary_name)

	step = FREQUENCY_STEP.get(missionary.support_frequency)
	if not step or not missionary.support_amount or not missionary.expense_type:
		return
	if not missionary.support_start_date:
		return

	today_date = getdate(today())
	end_date = getdate(missionary.support_end_date) if missionary.support_end_date else None

	# Anchor the next due date to the most recent expense already generated for
	# this missionary; fall back to the support start date for the first run.
	last_date = frappe.db.get_value(
		"Expense",
		filters={"missionary": missionary_name},
		fieldname="date",
		order_by="date desc",
	)
	if last_date:
		next_date = step(getdate(last_date))
	else:
		next_date = getdate(missionary.support_start_date)

	created = 0
	while next_date <= today_date and created < MAX_EXPENSES_PER_RUN:
		if end_date and next_date > end_date:
			break
		_create_expense(missionary, next_date)
		created += 1
		next_date = step(next_date)


def _create_expense(missionary, expense_date):
	expense = frappe.get_doc(
		{
			"doctype": "Expense",
			"title": f"Missionary Support: {missionary.title}",
			"amount": missionary.support_amount,
			"type": missionary.expense_type,
			"date": expense_date,
			"missionary": missionary.name,
			"notes": (
				f"Auto-generated {missionary.support_frequency} support for "
				f"{missionary.title}."
			),
		}
	)
	expense.insert(ignore_permissions=True)
