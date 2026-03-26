"""Church Chart of Accounts — applied after the setup wizard completes."""

import json
import os

import frappe

CHART_DIR = os.path.dirname(__file__)


def apply_church_chart(company):
	"""Replace the company's default Chart of Accounts with the church one.

	Deletes the Standard accounts that ERPNext created during company setup,
	then inserts the church-specific accounts from the bundled JSON template.
	Sets default receivable/payable accounts directly via DB to avoid
	triggering Company.on_update() (which would conflict with the wizard lock).
	"""
	from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import (
		create_charts,
	)
	from erpnext.accounts.doctype.chart_of_accounts_importer.chart_of_accounts_importer import (
		unset_existing_data,
	)

	chart_file = os.path.join(CHART_DIR, "church_chart_of_accounts.json")
	with open(chart_file) as f:
		chart_data = json.load(f)

	unset_existing_data(company)
	frappe.local.flags.ignore_root_company_validation = True
	create_charts(company, custom_chart=chart_data["tree"])

	# Set default accounts without calling company.save() to avoid re-triggering on_update.
	frappe.db.set_value("Company", company, {
		"default_receivable_account": frappe.db.get_value(
			"Account", {"company": company, "account_type": "Receivable", "is_group": 0}
		),
		"default_payable_account": frappe.db.get_value(
			"Account", {"company": company, "account_type": "Payable", "is_group": 0}
		),
	})
