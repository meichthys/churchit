# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The states and provinces that an Address can name.

Address `state` keeps text: ERPNext shares Address, and most countries have no list that their post
uses. For each country in `STATE_COUNTRIES`, the desk suggests the ISO 3166-2 states by full name (an
Autocomplete, `public/js/address.js`), and `set_state` stores a name or code typed anywhere (the
form, an import, a contact card, the API) as the full name and refuses any other value.
"""

import unicodedata
from functools import cache

import frappe
import pycountry
from frappe import _
from frappe.model.document import Document

# ISO 3166-1 codes of the countries whose ISO 3166-2 names are the ones their addresses use.
STATE_COUNTRIES = ("US", "CA", "AU")

# Postal states that ISO 3166-2 leaves out: US military mail.
MORE_STATES = {
	"US": {"AA": "Armed Forces Americas", "AE": "Armed Forces Europe", "AP": "Armed Forces Pacific"},
}


def get_full_state(country: str | None, state: str) -> str | None:
	"""The full name that *state* stands for in the Country *country*, by name or code in any case.

	*state* itself when the country has no list, and None when its list does not have it.
	"""
	code = get_listed_code(country)
	return get_states_of_code(code).get(fold(state)) if code else state


def get_listed_code(country: str | None) -> str | None:
	"""The ISO code of the Country *country* when it is in `STATE_COUNTRIES`, else None."""
	code = (frappe.get_cached_value("Country", country, "code") or "").upper() if country else ""
	return code if code in STATE_COUNTRIES else None


@cache
def get_states_of_code(country_code: str) -> dict[str, str]:
	"""The full name of each state of the ISO country *country_code*, keyed by its folded name and code."""
	states = {
		state.code.removeprefix(f"{country_code}-"): state.name
		for state in pycountry.subdivisions.get(country_code=country_code)
	}
	states.update(MORE_STATES.get(country_code, {}))
	return {fold(key): name for code, name in states.items() for key in (code, name)}


def fold(text: str) -> str:
	"""*text* for comparing: trimmed, in lower case and without accents, so Québec is Quebec."""
	text = unicodedata.normalize("NFKD", text.strip().casefold())
	return "".join(character for character in text if not unicodedata.combining(character))


@frappe.whitelist(methods=["GET"])
def get_state_names(country: str) -> list[str]:
	"""The full names of the states of *country*, empty when its addresses take any text. Reads only."""
	code = get_listed_code(country)
	return sorted(set(get_states_of_code(code).values())) if code else []


def set_state(address: Document, method: str | None = None) -> None:
	"""Store a new state of *address* as its full name, or refuse one that its country does not have."""
	if not address.state or not (address.has_value_changed("state") or address.has_value_changed("country")):
		return

	state = get_full_state(address.country, address.state)
	if not state:
		frappe.throw(
			_("{0} is not a state or province of {1}.").format(address.state, _(address.country)),
			title=_("Unknown State"),
		)
	address.state = state
