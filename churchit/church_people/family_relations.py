# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

ROLE_TYPES = {
	"spouse": ("Husband", "Wife"),
	"child": ("Son", "Daughter"),
	"parent": ("Father", "Mother"),
	"sibling": ("Brother", "Sister"),
	"grandchild": ("Grandson", "Granddaughter"),
	"grandparent": ("Grandfather", "Grandmother"),
	"nephew": ("Nephew", "Niece"),
	"uncle": ("Uncle", "Aunt"),
	"sibling_in_law": ("Brother-in-law", "Sister-in-law"),
	"parent_in_law": ("Father-in-law", "Mother-in-law"),
	"step_parent": ("Stepfather", "Stepmother"),
	"step_sibling": ("Stepbrother", "Stepsister"),
	"step_child": ("Stepson", "Stepdaughter"),
	"child_in_law": ("Son-in-law", "Daughter-in-law"),
	"cousin": ("Cousin", "Cousin"),
}
ROLE_OF_TYPE = {relation_type: role for role, types in ROLE_TYPES.items() for relation_type in types}

# What someone is to a person who has this role to them. The spouse link owns Husband/Wife.
INVERSE_ROLES = {
	"child": "parent",
	"parent": "child",
	"sibling": "sibling",
	"grandchild": "grandparent",
	"grandparent": "grandchild",
	"nephew": "uncle",
	"uncle": "nephew",
	"sibling_in_law": "sibling_in_law",
	"step_sibling": "step_sibling",
	"step_parent": "step_child",
	"step_child": "step_parent",
	"parent_in_law": "child_in_law",
	"child_in_law": "parent_in_law",
	"cousin": "cousin",
}

# What a member's spouse is to the head, from that member's role.
SPOUSE_ROLES = {
	"child": "child_in_law",
	"child_in_law": "child",
	"sibling": "sibling_in_law",
}

# (person's role, other's role) -> what the other is to the person, both roles read against the head.
# Pairs left out are ambiguous (two grandchildren may be siblings or cousins), so they get no row.
MEMBER_ROLE_FOR = {
	("child", "child"): "sibling",
	("child", "spouse"): "parent",
	("spouse", "child"): "child",
	("child", "parent"): "grandparent",
	("parent", "child"): "grandchild",
	("child", "sibling"): "uncle",
	("sibling", "child"): "nephew",
	("sibling", "sibling"): "sibling",
	("sibling", "parent"): "parent",
	("parent", "sibling"): "child",
	("spouse", "sibling"): "sibling_in_law",
	("sibling", "spouse"): "sibling_in_law",
	("spouse", "parent"): "parent_in_law",
	("spouse", "grandchild"): "grandchild",
	("grandchild", "spouse"): "grandparent",
	("spouse", "child_in_law"): "child_in_law",
	("child_in_law", "spouse"): "parent_in_law",
	("child", "child_in_law"): "sibling_in_law",
	("child_in_law", "child"): "sibling_in_law",
}


class FamilyRelations:
	"""Relations rows that a Family's 'Relationship to Head' labels imply between its members."""

	def __init__(self, family):
		self.head = family.head_of_household
		self.labels = {
			member.member: member.relationship_to_head for member in family.members if member.member
		}
		self.genders = dict(
			# church-scope: only this family's own members, by name
			frappe.get_all(
				"Person", filters={"name": ["in", list(self.labels)]}, fields=["name", "gender"], as_list=True
			)
		)
		self.relation_types = set(frappe.get_all("Person Relation Type", pluck="name"))
		self.hand_entered = self.get_hand_entered_types()

	def sync(self):
		for person in self.labels:
			set_family_relations(person, self.get_relations(person))

	def get_relations(self, person):
		"""(other person, relation type) pairs for *person*'s Relations table."""
		relations = []
		for other in self.labels:
			relation_type = other != person and self.get_relation_type(person, other)
			if relation_type in self.relation_types:
				relations.append((other, relation_type))
		return relations

	def get_hand_entered_types(self):
		"""{(person, other): relation type} for rows members entered by hand for each other."""
		members = list(self.labels)
		rows = frappe.get_all(
			"Person Relation",
			filters={
				"parenttype": "Person",
				"parent": ["in", members],
				"person": ["in", members],
				"from_family": 0,
			},
			fields=["parent", "person", "type"],
		)
		return {(row.parent, row.person): row.type for row in rows}

	def get_relation_type(self, person, other):
		"""What *other* is to *person*, or None when the labels do not say.

		A row *other* entered by hand for *person* wins over the labels, so both sides agree.
		"""
		entered_by_other = self.hand_entered.get((other, person))
		if entered_by_other:
			role = INVERSE_ROLES.get(ROLE_OF_TYPE.get(entered_by_other))
		elif person == self.head:
			label = self.labels[other]
			return None if ROLE_OF_TYPE.get(label) == "spouse" else label
		elif other == self.head:
			role = INVERSE_ROLES.get(self.get_role(person))
		else:
			role = MEMBER_ROLE_FOR.get((self.get_role(person), self.get_role(other)))
		return get_gendered_type(role, self.genders.get(other))

	def get_role(self, person):
		return ROLE_OF_TYPE.get(self.labels[person])


def get_spouse_label(partner_label, gender):
	"""Relationship to Head for the spouse of a member labelled *partner_label*, e.g. a Son's wife is a Daughter-in-law."""
	return get_gendered_type(SPOUSE_ROLES.get(ROLE_OF_TYPE.get(partner_label)), gender)


def get_gendered_type(role, gender):
	"""The relation type for *role* that fits *gender*, or None when *gender* decides it and is unknown."""
	if not role:
		return None
	male, female = ROLE_TYPES[role]
	if male == female:
		return male
	return {"Male": male, "Female": female}.get(gender)


def keep_relations_of(leavers):
	"""Make From Family rows to and from people leaving the family hand-entered, since the relationships still hold."""
	if not leavers:
		return
	for fieldname in ("parent", "person"):
		frappe.db.set_value(
			"Person Relation",
			{"parenttype": "Person", fieldname: ["in", leavers], "from_family": 1},
			"from_family",
			0,
		)


def set_family_relations(person_name, relations):
	"""Replace *person_name*'s From Family rows with *relations*. A hand-entered row for the same person wins."""
	person = frappe.get_doc("Person", person_name)
	hand_entered = [row for row in person.relations if not row.from_family]
	people_entered_by_hand = {row.person for row in hand_entered}
	relations = sorted(relation for relation in relations if relation[0] not in people_entered_by_hand)
	if relations == sorted((row.person, row.type) for row in person.relations if row.from_family):
		return
	person.set("relations", hand_entered)
	for other, relation_type in relations:
		person.append("relations", {"person": other, "type": relation_type, "from_family": 1})
	for idx, row in enumerate(person.relations, 1):
		row.idx = idx
	person.update_child_table("relations")
