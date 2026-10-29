# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Mark every Fund that existed before Tax Deductible as tax deductible, so their gifts stay on statements.

The column default already gives existing rows 1. When no Fund has 1, the default did not apply, so tick
them all. When any Fund has 1, do nothing, so a run again keeps the funds a user unticked.
"""

import frappe


def execute():
	if frappe.db.exists("Fund", {"is_tax_deductible": 1}):
		return

	Fund = frappe.qb.DocType("Fund")
	frappe.qb.update(Fund).set(Fund.is_tax_deductible, 1).run()
