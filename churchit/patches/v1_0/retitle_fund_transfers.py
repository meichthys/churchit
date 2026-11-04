# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Title each fund transfer with the names of its funds, 'General to Building', not their IDs and a date."""

import frappe

from churchit.church_finances.doctype.fund_transfer.fund_transfer import get_title


def execute():
	for transfer in frappe.get_all("Fund Transfer", fields=["name", "from_fund", "to_fund"]):
		title = get_title(transfer.from_fund, transfer.to_fund)
		frappe.db.set_value("Fund Transfer", transfer.name, "title", title, update_modified=False)
