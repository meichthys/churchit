# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.model.document import Document


class PersonRelationship(Document):
	"""A relationship to a person in another household, kept on one person only.

	The other person sees it in their Connections. `Person.validate_relationships` checks each new row.
	"""
