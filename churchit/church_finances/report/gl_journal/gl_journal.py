# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate

from churchit.church_scope import is_multi_church, root_church, scoped


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	if not (filters.get("from_date") and filters.get("to_date")):
		return columns, []

	return columns, Journal(filters).get_rows()


def get_columns():
	return [
		{"fieldname": "date", "fieldtype": "Date", "label": _("Date"), "width": 110},
		{"fieldname": "account", "fieldtype": "Data", "label": _("Account"), "width": 200},
		{"fieldname": "debit", "fieldtype": "Currency", "label": _("Debit"), "width": 130},
		{"fieldname": "credit", "fieldtype": "Currency", "label": _("Credit"), "width": 130},
		{"fieldname": "memo", "fieldtype": "Data", "label": _("Memo"), "width": 220},
	]


class Journal:
	"""Balanced debit and credit lines for the submitted Collections, Expenses and Fund Transfers in a date range.

	Each line takes its account from the GL Account Mapping of the source record's own church. The memo
	names the source document only: a title can hold a person's name (an Alms expense).
	"""

	def __init__(self, filters):
		self.filters = filters
		self.from_date = filters["from_date"]
		self.before_date = add_days(filters["to_date"], 1)
		self.multi_church = is_multi_church()
		self.precision = frappe.get_precision("Collection Fund Total", "total")
		self.accounts = self.get_accounts()
		self.missing = set()
		self.rows = []

	def get_rows(self):
		self.add_collections()
		self.add_expenses()
		self.add_fund_transfers()
		self.refuse_missing_mappings()
		return sorted(self.rows, key=lambda row: (row["date"], row["memo"], -row["debit"]))

	def get_accounts(self):
		Mapping = frappe.qb.DocType("GL Account Mapping")
		query = frappe.qb.from_(Mapping).select(
			Mapping.church, Mapping.mapping_for, Mapping.record, Mapping.account
		)
		accounts = {}
		for row in scoped(query, Mapping, self.filters).run(as_dict=True):
			key = (self.get_church(row.church), row.mapping_for, row.record)
			if key in accounts:
				frappe.throw(
					_("{0} {1} is mapped to more than one account: {2} and {3}.").format(
						_(row.mapping_for), row.record, accounts[key], row.account
					)
				)
			accounts[key] = row.account
		return accounts

	def get_church(self, church):
		"""The church whose mappings a record uses. A single-church site has one set of mappings."""
		return (church or "") if self.multi_church else ""

	def in_dates(self, table):
		return (table.docstatus == 1) & (table.date >= self.from_date) & (table.date < self.before_date)

	def add_collections(self):
		Collection = frappe.qb.DocType("Collection")
		debits = self.get_collection_totals(Collection, "Collection Payment Type Total", "payment_type")
		credits = self.get_collection_totals(Collection, "Collection Fund Total", "fund")
		for name, collection in credits.items():
			self.add_entry(
				collection,
				[("Payment Type", record, total) for record, total in debits.get(name, {}).get("lines", [])],
				[("Fund", record, total) for record, total in collection["lines"]],
			)

	def get_collection_totals(self, Collection, child_doctype, link_field):
		"""{collection: {name, date, church, lines: [(record, total)]}} from one of its totals tables."""
		Total = frappe.qb.DocType(child_doctype)
		query = (
			frappe.qb.from_(Total)
			.join(Collection)
			.on((Collection.name == Total.parent) & (Total.parenttype == "Collection"))
			.select(
				Collection.name,
				Collection.date,
				Collection.church,
				Total[link_field].as_("record"),
				Total.total,
			)
			.where(self.in_dates(Collection))
		)
		collections = {}
		for row in scoped(query, Collection, self.filters).run(as_dict=True):
			collection = collections.setdefault(row.name, {**row, "doctype": "Collection", "lines": []})
			collection["lines"].append((row.record, row.total))
		return collections

	def add_expenses(self):
		Expense = frappe.qb.DocType("Expense")
		query = (
			frappe.qb.from_(Expense)
			.select(Expense.name, Expense.date, Expense.church, Expense.type, Expense.amount)
			.where(self.in_dates(Expense))
		)
		for expense in scoped(query, Expense, self.filters).run(as_dict=True):
			self.add_entry(
				{**expense, "doctype": "Expense"},
				[("Expense Type", expense.type, expense.amount)],
				[("Church", expense.church or root_church(), expense.amount)],
			)

	def add_fund_transfers(self):
		Transfer = frappe.qb.DocType("Fund Transfer")
		query = (
			frappe.qb.from_(Transfer)
			.select(
				Transfer.name,
				Transfer.date,
				Transfer.church,
				Transfer.from_fund,
				Transfer.to_fund,
				Transfer.amount,
			)
			.where(self.in_dates(Transfer))
		)
		for transfer in scoped(query, Transfer, self.filters).run(as_dict=True):
			self.add_entry(
				{**transfer, "doctype": "Fund Transfer"},
				[("Fund", transfer.from_fund, transfer.amount)],
				[("Fund", transfer.to_fund, transfer.amount)],
			)

	def add_entry(self, source, debits, credits):
		"""Add one source document's lines, refusing a document whose debits and credits differ."""
		total_debit = flt(sum(amount for _doctype, _record, amount in debits), self.precision)
		total_credit = flt(sum(amount for _doctype, _record, amount in credits), self.precision)
		if total_debit != total_credit:
			frappe.throw(_("{0} {1} does not balance.").format(_(source["doctype"]), source["name"]))

		for lines, side in ((debits, "debit"), (credits, "credit")):
			for doctype, record, amount in lines:
				self.add_line(source, doctype, record, flt(amount, self.precision), side)

	def add_line(self, source, doctype, record, amount, side):
		church = self.get_church(source["church"])
		account = self.accounts.get((church, doctype, record))
		if not account:
			self.missing.add((church, doctype, record))
		self.rows.append(
			{
				"date": getdate(source["date"]),
				"account": account,
				"debit": amount if side == "debit" else 0,
				"credit": amount if side == "credit" else 0,
				"memo": f"{source['doctype']} {source['name']}",
			}
		)

	def refuse_missing_mappings(self):
		"""Throw one message that names every record with no account, so Finance can map them all at once."""
		if not self.missing:
			return
		items = "".join(
			f"<li>{self.describe(church, doctype, record)}</li>"
			for church, doctype, record in sorted(self.missing)
		)
		frappe.throw(
			_("Add a GL Account Mapping for each of these records:") + f"<ul>{items}</ul>",
			title=_("Missing GL Account Mappings"),
		)

	def describe(self, church, doctype, record):
		title_field = frappe.get_meta(doctype).title_field
		title = (title_field and frappe.db.get_value(doctype, record, title_field)) or record
		label = f"{_(doctype)} {frappe.bold(title)}"
		if not church:
			return label
		return _("{0} for {1}").format(label, frappe.db.get_value("Church", church, "church_name"))
