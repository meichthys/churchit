"""Church Directory Report"""

import calendar

import frappe
from frappe.utils import today as frappe_today

from church.utils import set_report_link_titles

_TEMPLATE_PATH = "church/church_people/report/church_directory_report/church_directory.html"


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

	return frappe.db.sql(
		"""
		SELECT
			p.name AS person,
			p.family,
			p.primary_phone,
			p.email,
			COALESCE(a.city, '') AS city,
			COALESCE(a.state, '') AS state
		FROM `tabPerson` p
		LEFT JOIN `tabFamily` f ON f.name = p.family
		LEFT JOIN `tabAddress` a ON a.name = f.home_address
		WHERE (NOT %(members_only)s OR p.membership_status = 'Active')
		ORDER BY p.last_name, p.first_name
		""",
		{"members_only": members_only},
		as_dict=True,
	)


def get_data(filters):
	members_only = frappe.utils.cint((filters or {}).get("members_only", 0))

	families = frappe.db.sql(
		"""
		SELECT
			f.name AS family_id,
			f.family_name,
			COALESCE(a.city, '') AS city,
			COALESCE(a.state, '') AS state
		FROM `tabFamily` f
		LEFT JOIN `tabAddress` a ON a.name = f.home_address
		ORDER BY f.family_name ASC
		""",
		as_dict=True,
	)

	all_members = frappe.db.sql(
		"""
		SELECT p.name, p.full_name, p.family, p.is_head_of_household
		FROM `tabPerson` p
		WHERE p.family IS NOT NULL AND p.family != ''
			AND (NOT %(members_only)s OR p.membership_status = 'Active')
		""",
		{"members_only": members_only},
		as_dict=True,
	)

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

	families = frappe.db.sql(
		"""
		SELECT
			f.name AS family_id,
			f.family_name,
			f.photo AS family_photo,
			COALESCE(a.address_line1, '') AS address_line1,
			COALESCE(a.address_line2, '') AS address_line2,
			COALESCE(a.city, '') AS city,
			COALESCE(a.state, '') AS state,
			COALESCE(a.pincode, '') AS pincode
		FROM `tabFamily` f
		LEFT JOIN `tabAddress` a ON a.name = f.home_address
		ORDER BY f.family_name ASC
		""",
		as_dict=True,
	)

	all_members = frappe.db.sql(
		"""
		SELECT
			p.name AS person_name,
			p.full_name,
			p.last_name,
			p.primary_phone,
			p.email,
			p.membership_status,
			p.is_head_of_household,
			p.gender,
			p.spouse,
			p.photo,
			p.family
		FROM `tabPerson` p
		WHERE p.family IS NOT NULL AND p.family != ''
			AND (NOT %(members_only)s OR p.membership_status = 'Active')
		ORDER BY p.family, p.is_head_of_household DESC, p.last_name, p.first_name
		""",
		{"members_only": members_only},
		as_dict=True,
	)

	# Fetch active positions if requested
	roles_by_person = {}
	if show_roles:
		today = frappe_today()
		active_positions = frappe.db.sql(
			"""
			SELECT pos.parent AS person_name, COALESCE(pt.position, pos.position) AS position
			FROM `tabPosition` pos
			INNER JOIN `tabPerson` p ON p.name = pos.parent
			LEFT JOIN `tabPosition Type` pt ON pt.name = pos.position
			WHERE pos.parenttype = 'Person'
				AND pos.position IS NOT NULL
				AND pos.start_date <= %(today)s
				AND (pos.end_date IS NULL OR pos.end_date >= %(today)s)
			ORDER BY pos.parent, pos.start_date
			""",
			{"today": today},
			as_dict=True,
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
		for row in frappe.db.sql(
			"""
			SELECT pr.parent AS hoh, pr.person AS other, pr.type AS relation_type
			FROM `tabPerson Relation` pr
			WHERE pr.parenttype = 'Person' AND pr.parent IN %(hoh)s
			""",
			{"hoh": tuple(hoh_names)},
			as_dict=True,
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
					"Wife" if m.gender == "Female"
					else "Husband" if m.gender == "Male"
					else "Spouse"
				)
			else:
				m["relation_to_hoh"] = hoh_relations.get((hoh.person_name, m.person_name), "")

	individuals_raw = frappe.db.sql(
		"""
		SELECT
			p.name AS person_name,
			p.full_name,
			p.last_name,
			p.primary_phone,
			p.email,
			p.membership_status,
			p.photo
		FROM `tabPerson` p
		WHERE (p.family IS NULL OR p.family = '')
			AND (NOT %(members_only)s OR p.membership_status = 'Active')
		ORDER BY p.last_name, p.first_name
		""",
		{"members_only": members_only},
		as_dict=True,
	)

	for p in individuals_raw:
		p["positions"] = roles_by_person.get(p.person_name, [])
		p["is_head_of_household"] = 0

	# Resolve membership_status hashes to human-readable status labels
	all_people = list(all_members) + list(individuals_raw)
	status_names = list({p.membership_status for p in all_people if p.membership_status})
	status_map = {}
	if status_names:
		for row in frappe.get_all("Member Status", filters=[["name", "in", status_names]], fields=["name", "status"]):
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
		raw_birthdays = frappe.db.sql(
			"""
			SELECT
				p.full_name,
				le.date AS birthday,
				MONTH(le.date) AS birth_month,
				DAY(le.date)   AS birth_day
			FROM `tabPerson` p
			JOIN `tabLife Event` le
				ON le.parent = p.name
				AND le.parenttype = 'Person'
				AND le.event_type = 'Birth'
			WHERE le.date IS NOT NULL
				AND (NOT %(members_only)s OR p.membership_status = 'Active')
			ORDER BY MONTH(le.date), DAY(le.date), p.last_name, p.first_name
			""",
			{"members_only": members_only},
			as_dict=True,
		)
		for row in raw_birthdays:
			row["month_name"] = calendar.month_name[int(row.birth_month)]
			row["month_day"] = f"{calendar.month_name[int(row.birth_month)]} {int(row.birth_day)}"
			birthdays.append(row)

	# ── Anniversaries ────────────────────────────────────────────
	anniversaries = []
	if show_anniversaries:
		raw_anniversaries = frappe.db.sql(
			"""
			SELECT
				p.name         AS person_name,
				p.spouse       AS spouse_name,
				p.first_name   AS person_first,
				p.full_name    AS person_full,
				s.first_name   AS spouse_first,
				COALESCE(f.family_name, '') AS family_name,
				p.anniversary,
				MONTH(p.anniversary) AS ann_month,
				DAY(p.anniversary)   AS ann_day
			FROM `tabPerson` p
			LEFT JOIN `tabPerson` s ON s.name = p.spouse
			LEFT JOIN `tabFamily` f ON f.name = p.family
			WHERE p.anniversary IS NOT NULL
				AND p.is_married = 1
				AND (NOT %(members_only)s OR p.membership_status = 'Active')
			ORDER BY MONTH(p.anniversary), DAY(p.anniversary), p.last_name, p.first_name
			""",
			{"members_only": members_only},
			as_dict=True,
		)
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
		missionaries = frappe.db.sql(
			"""
			SELECT
				m.title,
				m.agency,
				m.country,
				m.email,
				m.website,
				m.photo,
				m.sensitive,
				m.mission_statement
			FROM `tabMissionary` m
			ORDER BY m.title
			""",
			as_dict=True,
		)
		# Resolve agency hashes to human-readable agency names
		agency_names = list({m.agency for m in missionaries if m.agency})
		if agency_names:
			agency_map = {
				row.name: row.agency_name
				for row in frappe.get_all(
					"Missionary Agency", filters=[["name", "in", agency_names]], fields=["name", "agency_name"]
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

	template = frappe.get_jinja_environment().get_template(_TEMPLATE_PATH)
	return template.render(context)
