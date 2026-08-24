"""Church Directory Report"""

import calendar

import frappe
from frappe.query_builder.functions import Coalesce
from frappe.utils import today as frappe_today
from pypika import Order

from churchit.contacts import primary_address_query, primary_email_query, primary_phone_query
from churchit.query import Day, Month
from churchit.utils import set_report_link_titles


def execute(filters=None):
	group_by_family = frappe.utils.cint((filters or {}).get("group_by_family", 1))
	if group_by_family:
		columns = get_columns()
		data = get_data(filters)
	else:
		columns = get_individual_columns()
		data = get_individual_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "family", "fieldtype": "Link", "label": "Family", "options": "Family", "width": 200},
		{
			"fieldname": "head_of_household",
			"fieldtype": "Link",
			"label": "Head of Household",
			"options": "Person",
			"width": 180,
		},
		{"fieldname": "city", "fieldtype": "Data", "label": "City", "width": 140},
		{"fieldname": "state", "fieldtype": "Data", "label": "State", "width": 100},
		{"fieldname": "member_count", "fieldtype": "Int", "label": "Members", "width": 80},
	]


def get_individual_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "family", "fieldtype": "Link", "label": "Family", "options": "Family", "width": 160},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 180},
		{"fieldname": "city", "fieldtype": "Data", "label": "City", "width": 120},
		{"fieldname": "state", "fieldtype": "Data", "label": "State", "width": 100},
	]


def get_individual_data(filters):
	members_only = frappe.utils.cint((filters or {}).get("members_only", 0))

	Person = frappe.qb.DocType("Person")
	Family = frappe.qb.DocType("Family")
	Address = frappe.qb.DocType("Address")

	query = (
		frappe.qb.from_(Person)
		.left_join(Family)
		.on(Family.name == Person.family)
		.left_join(Address)
		.on(Address.name == Coalesce(primary_address_query(Person), primary_address_query(Family, "Family")))
		.select(
			Person.name.as_("person"),
			Person.family,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
			Coalesce(Address.city, "").as_("city"),
			Coalesce(Address.state, "").as_("state"),
		)
		.orderby(Person.last_name)
		.orderby(Person.first_name)
	)
	if members_only:
		query = query.where(Person.membership_status == "Active")

	return query.run(as_dict=True)


def get_data(filters):
	members_only = frappe.utils.cint((filters or {}).get("members_only", 0))

	Family = frappe.qb.DocType("Family")
	Address = frappe.qb.DocType("Address")
	Person = frappe.qb.DocType("Person")

	families = (
		frappe.qb.from_(Family)
		.left_join(Address)
		.on(Address.name == primary_address_query(Family, "Family"))
		.select(
			Family.name.as_("family_id"),
			Family.family_name,
			Coalesce(Address.city, "").as_("city"),
			Coalesce(Address.state, "").as_("state"),
		)
		.orderby(Family.family_name)
		.run(as_dict=True)
	)

	members_query = (
		frappe.qb.from_(Person)
		.select(Person.name, Person.full_name, Person.family, Person.is_head_of_household)
		.where(Person.family.isnotnull() & (Person.family != ""))
	)
	if members_only:
		members_query = members_query.where(Person.membership_status == "Active")

	all_members = members_query.run(as_dict=True)

	members_by_family = {}
	for m in all_members:
		members_by_family.setdefault(m.family, []).append(m)

	result = []
	for family in families:
		members = members_by_family.get(family.family_id, [])
		head = next((m.name for m in members if m.is_head_of_household), None)
		if not head and members:
			head = members[0].name
		result.append(
			{
				"family": family.family_id,
				"head_of_household": head or "",
				"city": family.city,
				"state": family.state,
				"member_count": len(members),
			}
		)

	return result


@frappe.whitelist()
def get_directory_html(
	members_only=0,
	group_by_family=1,
	show_photos=0,
	show_roles=0,
	show_membership=1,
	show_hoh=1,
	show_birthdays=0,
	show_anniversaries=0,
	show_missionaries=0,
):
	"""Generate the full HTML for the church directory, ready to print."""
	members_only = frappe.utils.cint(members_only)
	group_by_family = frappe.utils.cint(group_by_family)
	show_photos = frappe.utils.cint(show_photos)
	show_roles = frappe.utils.cint(show_roles)
	show_membership = frappe.utils.cint(show_membership)
	show_hoh = frappe.utils.cint(show_hoh)
	show_birthdays = frappe.utils.cint(show_birthdays)
	show_anniversaries = frappe.utils.cint(show_anniversaries)
	show_missionaries = frappe.utils.cint(show_missionaries)

	church_name = frappe.db.get_value("Church", {}, "name")
	church_doc = frappe.get_doc("Church", church_name) if church_name else None
	church_address = None
	if church_doc and church_doc.address:
		church_address = frappe.get_doc("Address", church_doc.address)

	Family = frappe.qb.DocType("Family")
	Address = frappe.qb.DocType("Address")
	Person = frappe.qb.DocType("Person")

	families = (
		frappe.qb.from_(Family)
		.left_join(Address)
		.on(Address.name == primary_address_query(Family, "Family"))
		.select(
			Family.name.as_("family_id"),
			Family.family_name,
			Family.photo.as_("family_photo"),
			Coalesce(Address.address_line1, "").as_("address_line1"),
			Coalesce(Address.address_line2, "").as_("address_line2"),
			Coalesce(Address.city, "").as_("city"),
			Coalesce(Address.state, "").as_("state"),
			Coalesce(Address.pincode, "").as_("pincode"),
		)
		.orderby(Family.family_name)
		.run(as_dict=True)
	)

	members_query = (
		frappe.qb.from_(Person)
		.select(
			Person.name.as_("person_name"),
			Person.full_name,
			Person.last_name,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
			Person.membership_status,
			Person.is_head_of_household,
			Person.gender,
			Person.spouse,
			Person.photo,
			Person.family,
		)
		.where(Person.family.isnotnull() & (Person.family != ""))
		.orderby(Person.family)
		.orderby(Person.is_head_of_household, order=Order.desc)
		.orderby(Person.last_name)
		.orderby(Person.first_name)
	)
	if members_only:
		members_query = members_query.where(Person.membership_status == "Active")

	all_members = members_query.run(as_dict=True)

	# Fetch active positions if requested
	roles_by_person = {}
	if show_roles:
		today = frappe_today()
		Position = frappe.qb.DocType("Position")
		PositionType = frappe.qb.DocType("Position Type")
		active_positions = (
			frappe.qb.from_(Position)
			.join(Person)
			.on(Person.name == Position.parent)
			.left_join(PositionType)
			.on(PositionType.name == Position.position)
			.select(
				Position.parent.as_("person_name"),
				Coalesce(PositionType.position, Position.position).as_("position"),
			)
			.where(
				(Position.parenttype == "Person")
				& Position.position.isnotnull()
				& (Position.start_date <= today)
				& (Position.end_date.isnull() | (Position.end_date >= today))
			)
			.orderby(Position.parent)
			.orderby(Position.start_date)
			.run(as_dict=True)
		)
		for row in active_positions:
			roles_by_person.setdefault(row.person_name, []).append(row.position)

	for m in all_members:
		m["positions"] = roles_by_person.get(m.person_name, [])

	members_by_family = {}
	for m in all_members:
		members_by_family.setdefault(m.family, []).append(m)

	# Compute each non-HoH member's relation to the head of household. Uses
	# the spouse field for husband/wife, then falls back to the Person
	# Relation child table (children, parents, siblings, etc.).
	hoh_by_family = {}
	for family_id, members in members_by_family.items():
		hoh = next((m for m in members if m.is_head_of_household), None) or (members[0] if members else None)
		if hoh:
			hoh_by_family[family_id] = hoh

	hoh_names = [h.person_name for h in hoh_by_family.values()]
	hoh_relations = {}
	if hoh_names:
		Relation = frappe.qb.DocType("Person Relation")
		for row in (
			frappe.qb.from_(Relation)
			.select(
				Relation.parent.as_("hoh"),
				Relation.person.as_("other"),
				Relation.type.as_("relation_type"),
			)
			.where((Relation.parenttype == "Person") & Relation.parent.isin(hoh_names))
			.run(as_dict=True)
		):
			hoh_relations[(row.hoh, row.other)] = row.relation_type

	for family_id, members in members_by_family.items():
		hoh = hoh_by_family.get(family_id)
		if not hoh:
			continue
		for m in members:
			if m.person_name == hoh.person_name:
				m["relation_to_hoh"] = ""
				continue
			if hoh.spouse and m.person_name == hoh.spouse:
				m["relation_to_hoh"] = (
					"Wife" if m.gender == "Female" else "Husband" if m.gender == "Male" else "Spouse"
				)
			else:
				m["relation_to_hoh"] = hoh_relations.get((hoh.person_name, m.person_name), "")

	individuals_query = (
		frappe.qb.from_(Person)
		.select(
			Person.name.as_("person_name"),
			Person.full_name,
			Person.last_name,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
			Person.membership_status,
			Person.photo,
		)
		.where(Person.family.isnull() | (Person.family == ""))
		.orderby(Person.last_name)
		.orderby(Person.first_name)
	)
	if members_only:
		individuals_query = individuals_query.where(Person.membership_status == "Active")

	individuals_raw = individuals_query.run(as_dict=True)

	for p in individuals_raw:
		p["positions"] = roles_by_person.get(p.person_name, [])
		p["is_head_of_household"] = 0

	# Resolve membership_status hashes to human-readable status labels
	all_people = list(all_members) + list(individuals_raw)
	status_names = list({p.membership_status for p in all_people if p.membership_status})
	status_map = {}
	if status_names:
		for row in frappe.get_all(
			"Member Status", filters=[["name", "in", status_names]], fields=["name", "status"]
		):
			status_map[row.name] = row.status
	for p in all_people:
		if p.membership_status:
			p["membership_status"] = status_map.get(p.membership_status, p.membership_status)
		else:
			p["membership_status"] = "Non-Member"

	# Build merged sorted entry list
	all_entries = []

	if group_by_family:
		for family in families:
			members = members_by_family.get(family.family_id, [])
			if members:
				all_entries.append(
					{
						"sort_name": family.family_name,
						"display_name": family.family_name + " Family",
						"is_individual": False,
						"family_photo": family.family_photo,
						"address_line1": family.address_line1,
						"address_line2": family.address_line2,
						"city": family.city,
						"state": family.state,
						"pincode": family.pincode,
						"members": members,
					}
				)

		for person in individuals_raw:
			sort_key = (person.get("last_name") or person.get("full_name") or "").strip()
			all_entries.append(
				{
					"sort_name": sort_key,
					"display_name": person.full_name,
					"is_individual": True,
					"family_photo": None,
					"address_line1": "",
					"address_line2": "",
					"city": "",
					"state": "",
					"pincode": "",
					"members": [person],
				}
			)
	else:
		# Flat list: every person is their own entry
		all_people = list(all_members) + list(individuals_raw)
		# Fetch address info for family members
		family_address = {}
		for family in families:
			family_address[family.family_id] = family

		for person in all_people:
			sort_key = (person.get("last_name") or person.get("full_name") or "").strip()
			fam = family_address.get(person.get("family"))
			all_entries.append(
				{
					"sort_name": sort_key,
					"display_name": person.full_name,
					"is_individual": True,
					"family_photo": None,
					"address_line1": fam.address_line1 if fam else "",
					"address_line2": fam.address_line2 if fam else "",
					"city": fam.city if fam else "",
					"state": fam.state if fam else "",
					"pincode": fam.pincode if fam else "",
					"members": [person],
				}
			)

	all_entries.sort(key=lambda e: (e["sort_name"] or "").upper())

	# ── Birthdays ────────────────────────────────────────────────
	birthdays = []
	if show_birthdays:
		LifeEvent = frappe.qb.DocType("Life Event")
		birthdays_query = (
			frappe.qb.from_(Person)
			.join(LifeEvent)
			.on(
				(LifeEvent.parent == Person.name)
				& (LifeEvent.parenttype == "Person")
				& (LifeEvent.event_type == "Birth")
			)
			.select(
				Person.full_name,
				LifeEvent.date.as_("birthday"),
				Month(LifeEvent.date).as_("birth_month"),
				Day(LifeEvent.date).as_("birth_day"),
			)
			.where(LifeEvent.date.isnotnull())
			.orderby(Month(LifeEvent.date))
			.orderby(Day(LifeEvent.date))
			.orderby(Person.last_name)
			.orderby(Person.first_name)
		)
		if members_only:
			birthdays_query = birthdays_query.where(Person.membership_status == "Active")

		raw_birthdays = birthdays_query.run(as_dict=True)
		for row in raw_birthdays:
			row["month_name"] = calendar.month_name[int(row.birth_month)]
			row["month_day"] = f"{calendar.month_name[int(row.birth_month)]} {int(row.birth_day)}"
			birthdays.append(row)

	# ── Anniversaries ────────────────────────────────────────────
	anniversaries = []
	if show_anniversaries:
		Spouse = frappe.qb.DocType("Person").as_("spouse")
		anniversaries_query = (
			frappe.qb.from_(Person)
			.left_join(Spouse)
			.on(Spouse.name == Person.spouse)
			.left_join(Family)
			.on(Family.name == Person.family)
			.select(
				Person.name.as_("person_name"),
				Person.spouse.as_("spouse_name"),
				Person.first_name.as_("person_first"),
				Person.full_name.as_("person_full"),
				Spouse.first_name.as_("spouse_first"),
				Coalesce(Family.family_name, "").as_("family_name"),
				Person.anniversary,
				Month(Person.anniversary).as_("ann_month"),
				Day(Person.anniversary).as_("ann_day"),
			)
			.where(Person.anniversary.isnotnull() & (Person.is_married == 1))
			.orderby(Month(Person.anniversary))
			.orderby(Day(Person.anniversary))
			.orderby(Person.last_name)
			.orderby(Person.first_name)
		)
		if members_only:
			anniversaries_query = anniversaries_query.where(Person.membership_status == "Active")

		raw_anniversaries = anniversaries_query.run(as_dict=True)
		seen_persons = set()
		for row in raw_anniversaries:
			if row.person_name in seen_persons:
				continue
			seen_persons.add(row.person_name)
			if row.spouse_name:
				seen_persons.add(row.spouse_name)
			row["month_name"] = calendar.month_name[int(row.ann_month)]
			row["month_day"] = f"{calendar.month_name[int(row.ann_month)]} {int(row.ann_day)}"
			if row.spouse_first and row.family_name:
				row["display_name"] = f"{row.person_first} & {row.spouse_first} {row.family_name}"
			elif row.spouse_first:
				row["display_name"] = f"{row.person_full} & {row.spouse_first}"
			else:
				row["display_name"] = row.person_full
			anniversaries.append(row)

	# ── Missionaries ─────────────────────────────────────────────
	missionaries = []
	if show_missionaries:
		Missionary = frappe.qb.DocType("Missionary")
		missionaries = (
			frappe.qb.from_(Missionary)
			.select(
				Missionary.title,
				Missionary.agency,
				Missionary.country,
				primary_email_query(Missionary, "Missionary").as_("email"),
				Missionary.website,
				Missionary.photo,
				Missionary.sensitive,
				Missionary.mission_statement,
			)
			.orderby(Missionary.title)
			.run(as_dict=True)
		)
		# Resolve agency hashes to human-readable agency names
		agency_names = list({m.agency for m in missionaries if m.agency})
		if agency_names:
			agency_map = {
				row.name: row.agency_name
				for row in frappe.get_all(
					"Missionary Agency",
					filters=[["name", "in", agency_names]],
					fields=["name", "agency_name"],
				)
			}
			for m in missionaries:
				if m.agency:
					m["agency"] = agency_map.get(m.agency, m.agency)

	context = {
		"church": church_doc,
		"church_address": church_address,
		"all_entries": all_entries,
		"show_church_label": False,
		"show_photos": show_photos,
		"show_roles": show_roles,
		"show_membership": show_membership,
		"show_hoh": show_hoh,
		"birthdays": birthdays,
		"anniversaries": anniversaries,
		"missionaries": missionaries,
		"show_birthdays": show_birthdays,
		"show_anniversaries": show_anniversaries,
		"show_missionaries": show_missionaries,
		"generated_date": frappe.utils.formatdate(frappe.utils.nowdate(), "MMMM yyyy"),
	}

	# Load the shipped template through the Jinja filesystem loader (path-only, so
	# no user-supplied string can ever be rendered as a template).
	return frappe.get_template(
		"churchit/church_people/report/church_directory_report/church_directory.html"
	).render(context)
