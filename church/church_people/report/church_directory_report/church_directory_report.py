"""Church Directory Report (AI Generated)"""

import calendar
import os

import frappe
from frappe.utils import today as frappe_today

from church.utils import build_in_clause, get_church_scope


def execute(filters=None):
	group_by_family = frappe.utils.cint((filters or {}).get("group_by_family", 1))
	if group_by_family:
		return get_columns(), get_data(filters)
	else:
		return get_individual_columns(), get_individual_data(filters)


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
		{"fieldname": "church", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 160},
		{"fieldname": "city", "fieldtype": "Data", "label": "City", "width": 140},
		{"fieldname": "state", "fieldtype": "Data", "label": "State", "width": 100},
		{"fieldname": "member_count", "fieldtype": "Int", "label": "Members", "width": 80},
	]


def get_individual_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "family", "fieldtype": "Link", "label": "Family", "options": "Family", "width": 160},
		{"fieldname": "church", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 160},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 180},
		{"fieldname": "city", "fieldtype": "Data", "label": "City", "width": 120},
		{"fieldname": "state", "fieldtype": "Data", "label": "State", "width": 100},
	]


def get_individual_data(filters):
	if not filters or not filters.get("church"):
		return []

	church = filters.get("church")
	members_only = frappe.utils.cint(filters.get("members_only", 0))
	include_sub_churches = frappe.utils.cint(filters.get("include_sub_churches", 0))

	churches = get_church_scope(church, include_sub_churches)
	church_in = build_in_clause(churches)

	member_filter = "AND p.is_member = 1" if members_only else ""

	return frappe.db.sql(
		f"""
		SELECT
			p.name AS person,
			p.family,
			p.church,
			p.primary_phone,
			p.email,
			COALESCE(a.city, '') AS city,
			COALESCE(a.state, '') AS state
		FROM `tabPerson` p
		LEFT JOIN `tabFamily` f ON f.name = p.family
		LEFT JOIN `tabAddress` a ON a.name = f.home_address
		WHERE p.church IN {church_in}
			{member_filter}
		ORDER BY p.last_name, p.first_name
		""",
		as_dict=True,
	)


def get_data(filters):
	if not filters or not filters.get("church"):
		return []

	church = filters.get("church")
	members_only = frappe.utils.cint(filters.get("members_only", 0))
	include_sub_churches = frappe.utils.cint(filters.get("include_sub_churches", 0))

	churches = get_church_scope(church, include_sub_churches)
	church_in = build_in_clause(churches)

	families = frappe.db.sql(
		f"""
		SELECT
			f.name AS family_id,
			f.family_name,
			f.church,
			COALESCE(a.city, '') AS city,
			COALESCE(a.state, '') AS state
		FROM `tabFamily` f
		LEFT JOIN `tabAddress` a ON a.name = f.home_address
		WHERE f.church IN {church_in}
		ORDER BY f.family_name ASC
		""",
		as_dict=True,
	)

	member_filter = "AND p.is_member = 1" if members_only else ""

	all_members = frappe.db.sql(
		f"""
		SELECT p.name, p.full_name, p.family, p.is_head_of_household
		FROM `tabPerson` p
		WHERE p.church IN {church_in}
			AND p.family IS NOT NULL AND p.family != ''
			{member_filter}
		""",
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
				"church": family.church,
				"city": family.city,
				"state": family.state,
				"member_count": len(members),
			}
		)

	return result


@frappe.whitelist()
def get_directory_html(
	church,
	members_only=0,
	include_sub_churches=0,
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
	include_sub_churches = frappe.utils.cint(include_sub_churches)
	group_by_family = frappe.utils.cint(group_by_family)
	show_photos = frappe.utils.cint(show_photos)
	show_roles = frappe.utils.cint(show_roles)
	show_membership = frappe.utils.cint(show_membership)
	show_hoh = frappe.utils.cint(show_hoh)
	show_birthdays = frappe.utils.cint(show_birthdays)
	show_anniversaries = frappe.utils.cint(show_anniversaries)
	show_missionaries = frappe.utils.cint(show_missionaries)

	frappe.has_permission("Church", doc=church, throw=True)
	church_doc = frappe.get_doc("Church", church)
	church_address = None
	if church_doc.address:
		church_address = frappe.get_doc("Address", church_doc.address)

	churches = get_church_scope(church, include_sub_churches)
	church_in = build_in_clause(churches)

	families = frappe.db.sql(
		f"""
		SELECT
			f.name AS family_id,
			f.family_name,
			c.church_name AS church_name,
			f.photo AS family_photo,
			COALESCE(a.address_line1, '') AS address_line1,
			COALESCE(a.address_line2, '') AS address_line2,
			COALESCE(a.city, '') AS city,
			COALESCE(a.state, '') AS state,
			COALESCE(a.pincode, '') AS pincode
		FROM `tabFamily` f
		LEFT JOIN `tabAddress` a ON a.name = f.home_address
		LEFT JOIN `tabChurch` c ON c.name = f.church
		WHERE f.church IN {church_in}
		ORDER BY f.family_name ASC
		""",
		as_dict=True,
	)

	member_filter = "AND p.is_member = 1" if members_only else ""

	all_members = frappe.db.sql(
		f"""
		SELECT
			p.name AS person_name,
			p.full_name,
			p.last_name,
			p.primary_phone,
			p.email,
			p.membership_status,
			p.is_head_of_household,
			p.photo,
			p.family,
			c.church_name AS church_name
		FROM `tabPerson` p
		LEFT JOIN `tabChurch` c ON c.name = p.church
		WHERE p.church IN {church_in}
			AND p.family IS NOT NULL AND p.family != ''
			{member_filter}
		ORDER BY p.family, p.is_head_of_household DESC, p.last_name, p.first_name
		""",
		as_dict=True,
	)

	# Fetch active positions if requested
	roles_by_person = {}
	if show_roles:
		today = frappe_today()
		active_positions = frappe.db.sql(
			f"""
			SELECT pos.parent AS person_name, pos.position
			FROM `tabPosition` pos
			INNER JOIN `tabPerson` p ON p.name = pos.parent
			WHERE pos.parenttype = 'Person'
				AND pos.position IS NOT NULL
				AND pos.start_date <= %(today)s
				AND (pos.end_date IS NULL OR pos.end_date >= %(today)s)
				AND p.church IN {church_in}
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

	individuals_raw = frappe.db.sql(
		f"""
		SELECT
			p.name AS person_name,
			p.full_name,
			p.last_name,
			p.primary_phone,
			p.email,
			p.membership_status,
			p.photo,
			c.church_name AS church_name
		FROM `tabPerson` p
		LEFT JOIN `tabChurch` c ON c.name = p.church
		WHERE p.church IN {church_in}
			AND (p.family IS NULL OR p.family = '')
			{member_filter}
		ORDER BY p.last_name, p.first_name
		""",
		as_dict=True,
	)

	for p in individuals_raw:
		p["positions"] = roles_by_person.get(p.person_name, [])
		p["is_head_of_household"] = 0

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
						"church_name": family.church_name,
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
					"church_name": person.church_name,
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
					"church_name": person.get("church_name", ""),
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
			f"""
			SELECT
				p.full_name,
				p.birthday,
				MONTH(p.birthday) AS birth_month,
				DAY(p.birthday)   AS birth_day
			FROM `tabPerson` p
			WHERE p.church IN {church_in}
				AND p.birthday IS NOT NULL
				{member_filter}
			ORDER BY MONTH(p.birthday), DAY(p.birthday), p.last_name, p.first_name
			""",
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
			f"""
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
			WHERE p.church IN {church_in}
				AND p.anniversary IS NOT NULL
				AND p.is_married = 1
				{member_filter}
			ORDER BY MONTH(p.anniversary), DAY(p.anniversary), p.last_name, p.first_name
			""",
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
			f"""
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
			WHERE m.church IN {church_in}
			ORDER BY m.title
			""",
			as_dict=True,
		)

	template_path = os.path.join(os.path.dirname(__file__), "church_directory.html")
	with open(template_path) as f:
		template = f.read()

	context = {
		"church": church_doc,
		"church_address": church_address,
		"all_entries": all_entries,
		"show_church_label": bool(include_sub_churches),
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

	return frappe.render_template(template, context)


