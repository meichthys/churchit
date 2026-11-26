# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.address_states import STATE_COUNTRIES, get_full_state

# ERPNext's Tax Rule matches an address by its exact state, so its states change with the addresses.
STATE_FIELDS = (
	("Address", "country", "state"),
	("Tax Rule", "billing_country", "billing_state"),
	("Tax Rule", "shipping_country", "shipping_state"),
)


def execute():
	"""Store each address state that its country lists by its full name, such as IL as Illinois."""
	countries = frappe.get_all(
		"Country", filters={"code": ("in", [code.lower() for code in STATE_COUNTRIES])}, pluck="name"
	)
	for doctype, country_field, state_field in STATE_FIELDS:
		if countries and frappe.db.table_exists(doctype):
			name_states_in_full(doctype, country_field, state_field, countries)


def name_states_in_full(doctype: str, country_field: str, state_field: str, countries: list[str]):
	table = frappe.qb.DocType(doctype)
	country, state = table[country_field], table[state_field]
	rows = (
		frappe.qb.from_(table)
		.select(country.as_("country"), state.as_("state"))
		.distinct()
		.where(country.isin(countries) & (state != ""))
		.run(as_dict=True)
	)
	for row in rows:
		if full_state := get_full_state(row.country, row.state):
			frappe.qb.update(table).set(state, full_state).where(
				(country == row.country) & (state == row.state)
			).run()
