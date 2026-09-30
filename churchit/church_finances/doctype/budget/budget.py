import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import add_months, add_years, cint, get_first_day, get_last_day, getdate, nowdate
from frappe.utils.nestedset import get_descendants_of

from churchit.church_scope import church_query_filters
from churchit.query import Date

COMPARISON_WINDOWS = ("Same Period Last Year", "Last Month", "Last Quarter", "Last 12 Months")


class Budget(Document):
	def validate(self):
		if getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("End Date cannot be before Start Date."))
		self.validate_lines()
		self.warn_on_overlapping_budgets()

	def before_save(self):
		self.budgeted_amount = sum(row.budgeted_amount or 0 for row in (self.lines or []))

	def validate_lines(self):
		expense_types = set()
		for row in self.lines or []:
			if row.expense_type in expense_types:
				frappe.throw(_("Expense Type {0} is listed more than once.").format(row.expense_type))
			expense_types.add(row.expense_type)
		self.warn_on_nested_lines(expense_types)

	def warn_on_nested_lines(self, expense_types):
		"""Actuals roll child types into their parent, so a parent and child line double count."""
		bounds = get_expense_type_bounds()
		for expense_type in sorted(expense_types):
			node = bounds.get(expense_type)
			nested = [
				other
				for other in sorted(expense_types)
				if node and other in bounds and node[0] < bounds[other][0] <= node[1]
			]
			if nested:
				frappe.msgprint(
					_(
						"{0} already includes the expenses of {1}, so the total spent counts them twice."
					).format(frappe.bold(expense_type), ", ".join(nested)),
					title=_("Overlapping Budget Lines"),
					indicator="orange",
				)

	def warn_on_overlapping_budgets(self):
		"""Warn about a budget covering the same dates, within the churches the saver can see.

		Another church's budget neither overlaps this one nor may be named to
		whoever is saving, so the scope is part of the question, not a guard.
		"""
		overlapping = frappe.get_all(
			"Budget",
			filters={
				"name": ("!=", self.name or ""),
				"start_date": ("<=", self.end_date),
				"end_date": (">=", self.start_date),
				**church_query_filters({}),
			},
			pluck="name",
		)
		if overlapping:
			frappe.msgprint(
				_(
					"These dates overlap {0}. Budget reports show one budget at a time, so spending is split across them."
				).format(", ".join(overlapping)),
				title=_("Overlapping Budget"),
				indicator="orange",
			)

	@frappe.whitelist()
	def get_progress(self, comparison: str | None = None):
		"""Per-line spending against this budget, optionally beside a comparison window."""
		start, end = getdate(self.start_date), getdate(self.end_date)
		elapsed = get_elapsed_fraction(start, end)
		bounds = get_expense_type_bounds()
		branches = bool(cint(self.include_branches))
		actuals = get_expense_totals(start, end, church=self.church, include_branches=branches)
		pending = get_expense_totals(start, end, docstatus=0, church=self.church, include_branches=branches)
		window = get_comparison_window(start, end, comparison)
		window_actuals = (
			get_expense_totals(*window, church=self.church, include_branches=branches) if window else {}
		)
		scale = get_window_scale(window, start, end)

		rows = []
		for line in self.lines or []:
			budgeted = line.budgeted_amount or 0
			actual = roll_up(actuals, line.expense_type, bounds)
			window_budget = budgeted * scale
			window_actual = roll_up(window_actuals, line.expense_type, bounds)
			rows.append(
				{
					"expense_type": line.expense_type,
					"budgeted": budgeted,
					"expected_to_date": budgeted * elapsed,
					"actual": actual,
					"pending": roll_up(pending, line.expense_type, bounds),
					"variance": budgeted - actual,
					"pct": (actual / budgeted * 100) if budgeted else 0,
					"status": _("Over Budget") if actual > budgeted else _("Under Budget"),
					"comparison_budget": window_budget,
					"comparison_actual": window_actual,
					"comparison_pct": (window_actual / window_budget * 100) if window_budget else 0,
				}
			)

		rows.sort(key=lambda row: row["expense_type"] or "")
		return {
			"rows": rows,
			"elapsed_fraction": elapsed,
			"comparison": comparison,
			"window": [str(window[0]), str(window[1])] if window else None,
		}

	@frappe.whitelist()
	def add_all_expense_types(self):
		existing = {row.expense_type for row in (self.lines or [])}
		types = frappe.get_all("Expense Type", filters={"is_group": 0}, pluck="name")
		added = 0
		for t in sorted(types):
			if t not in existing:
				self.append("lines", {"expense_type": t, "budgeted_amount": 0})
				added += 1
		self.before_save()
		return added


@frappe.whitelist()
def get_current_budget(filters: str | list | dict | None = None):
	"""The budget covering today, else the most recently started one, within the church scope."""
	today = nowdate()
	scope = church_query_filters(filters)
	covering = frappe.get_all(
		"Budget",
		filters={"start_date": ("<=", today), "end_date": (">=", today), **scope},
		order_by="start_date desc",
		limit=1,
		pluck="name",
	)
	if covering:
		return covering[0]
	latest = frappe.get_all("Budget", filters=scope, order_by="start_date desc", limit=1, pluck="name")
	return latest[0] if latest else None


def get_expense_type_bounds():
	"""Nested set bounds per expense type, used to roll child types into a parent."""
	return {
		row.name: (row.lft, row.rgt)
		for row in frappe.get_all("Expense Type", fields=["name", "lft", "rgt"])
		if row.lft is not None and row.rgt is not None
	}


def get_expense_totals(start, end, docstatus=1, church=None, include_branches=False):
	"""Expense amount per exact expense type within a date range.

	A budget tracks its own church. Tick *include_branches* to count what the
	churches beneath it spend as well, which is how a main church budgets for the
	whole organisation.
	"""
	# church-scope: anchored to the budget's own church, which every caller passes in
	Expense = frappe.qb.DocType("Expense")
	query = (
		frappe.qb.from_(Expense)
		.select(Expense.type.as_("expense_type"), Sum(Expense.amount).as_("total"))
		.where((Expense.docstatus == docstatus) & Date(Expense.date)[str(start) : str(end)])
		.groupby(Expense.type)
	)
	if church and include_branches:
		query = query.where(Expense.church.isin([church, *get_descendants_of("Church", church)]))
	elif church:
		query = query.where(Expense.church == church)
	return {row.expense_type: float(row.total or 0) for row in query.run(as_dict=True)}


def roll_up(totals, expense_type, bounds):
	"""Total for an expense type including every type below it in the tree."""
	node = bounds.get(expense_type)
	if not node:
		return totals.get(expense_type, 0.0)
	left, right = node
	return sum(
		amount for name, amount in totals.items() if name in bounds and left <= bounds[name][0] <= right
	)


def get_elapsed_fraction(start, end):
	"""Share of the budget period that has passed, clamped to 0-1."""
	total_days = (end - start).days + 1
	if total_days <= 0:
		return 1.0
	elapsed_days = (getdate(nowdate()) - start).days + 1
	return max(0.0, min(1.0, elapsed_days / total_days))


def get_comparison_window(start, end, comparison):
	"""Date range for a comparison view, or None when no comparison was asked for."""
	if comparison == "Same Period Last Year":
		return getdate(add_years(start, -1)), getdate(add_years(end, -1))

	today = getdate(nowdate())
	if comparison == "Last Month":
		previous_month = add_months(today, -1)
		return getdate(get_first_day(previous_month)), getdate(get_last_day(previous_month))
	if comparison == "Last Quarter":
		quarter_start = getdate(f"{today.year}-{((today.month - 1) // 3) * 3 + 1:02d}-01")
		previous_quarter = getdate(add_months(quarter_start, -3))
		return previous_quarter, getdate(get_last_day(add_months(previous_quarter, 2)))
	if comparison == "Last 12 Months":
		return getdate(add_months(today, -12)), today
	return None


def get_window_scale(window, start, end):
	"""Share of the budget period a comparison window covers, for prorating amounts."""
	if not window:
		return 0.0
	period_days = (end - start).days + 1
	if period_days <= 0:
		return 0.0
	return ((window[1] - window[0]).days + 1) / period_days
