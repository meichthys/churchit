"""Move each Missionary's single Person link into its People table."""

import frappe


def execute():
	if not frappe.db.has_column("Missionary", "person"):
		return
	Missionary = frappe.qb.DocType("Missionary")
	Row = frappe.qb.DocType("Missionary Person")
	listed = set(frappe.qb.from_(Row).select(Row.parent, Row.person).run())
	missionaries = (
		frappe.qb.from_(Missionary)
		.select(Missionary.name, Missionary.person)
		.where(Missionary.person.isnotnull() & (Missionary.person != ""))
		.run()
	)
	for name, person in set(missionaries) - listed:
		frappe.get_doc(
			{
				"doctype": "Missionary Person",
				"parent": name,
				"parenttype": "Missionary",
				"parentfield": "people",
				"person": person,
				"idx": 1,
			}
		).db_insert()
