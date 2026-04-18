"""
Sample data for the Church app.

Creates a realistic set of sample records so new users can explore the app
immediately after installation.  Intended to be called from the setup wizard
when the user opts in to sample data.

All inserts are idempotent — safe to run more than once on the same site.
"""

import frappe
from frappe.utils import add_days, add_months, getdate

from church.patches.after_install import DEFAULT_CHURCH_NAME

# Ordered deletion steps: (is_submittable, doctype, filters).
# Prayer Request comments are handled separately after this list runs.
_DELETE_STEPS = [
	(False, "Church Task", {}),
	(False, "Church Asset", {}),
	(False, "Location", {}),
	(False, "Song", {}),
	(False, "Prayer", {}),
	(True, "Fund Transfer", {}),
	(False, "Ministry", {"ministry_name": ["!=", "General"]}),
	(False, "Group", {}),
	(False, "Belief", {}),
	(False, "Sermon", {}),
	(False, "Bible Reference", {}),
	(False, "Bible Verse", {}),
	(False, "Function", {}),
	(False, "Alms Request", {}),
	(False, "Prayer Request", {}),
	(True, "Expense", {}),
	(False, "Expense Type", {}),
	(True, "Collection", {}),
	(False, "Fund", {}),
	(False, "Missionary", {}),
	(False, "Missionary Agency", {}),
	(False, "Family", {}),
	(False, "Person", {}),
]

# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def setup_wizard_complete(args):
	"""Hook called by Frappe's setup wizard on completion.

	Creates sample data when the user opts in during setup.
	"""
	if args and args.get("create_sample_data"):
		create_sample_data()


@frappe.whitelist()
def create():
	"""Whitelisted method to create sample data from the browser console.

	Usage:  frappe.call("church.setup.sample_data.create")
	"""
	frappe.only_for("System Manager")
	create_sample_data()
	frappe.msgprint("Sample data has been created.", indicator="green", alert=True)


@frappe.whitelist()
def delete():
	"""Whitelisted method to remove sample data.

	Usage:  frappe.call("church.setup.sample_data.delete")
	"""
	frappe.only_for("System Manager")
	delete_sample_data()
	frappe.msgprint("Sample data has been removed.", indicator="green", alert=True)


def create_sample_data():
	"""Create all sample data in dependency order."""
	church = frappe.db.get_value("Church", {"church_name": DEFAULT_CHURCH_NAME}, "name")
	if not church:
		frappe.throw(f"Default church '{DEFAULT_CHURCH_NAME}' not found. Run after_install first.")

	position_refs = _create_positions()
	people = _create_people(position_refs)
	_create_church_manager_user(people)

	families = _create_families()
	_assign_families(people, families)
	_assign_spouses(people)

	agencies = _create_missionary_agencies()
	_create_missionaries(people, agencies)

	funds = _create_funds()
	expense_types = _create_expense_types(funds)
	group_roles = _get_group_role_refs()

	_create_collections(people, funds)
	_create_expenses(expense_types)

	_create_prayer_requests(people)
	_create_alms_requests(people)

	_create_functions()

	verses = _create_bible_verses()
	_create_bible_references(verses)

	_create_sermons(people)

	_create_beliefs(verses)

	groups = _create_groups(people, group_roles)

	_create_ministries(groups)

	_create_fund_transfers(funds)

	_create_prayers(people)

	_create_songs()

	locations = _create_locations()
	_create_church_assets(locations)

	_create_church_tasks(people)

	frappe.db.commit()


def delete_sample_data():
	"""Execute all deletion steps"""
	church = frappe.db.get_value("Church", {"church_name": DEFAULT_CHURCH_NAME}, "name")
	if not church:
		frappe.throw(f"Default church '{DEFAULT_CHURCH_NAME}' not found.")

	for submittable, doctype, filters in _DELETE_STEPS:
		if submittable:
			_delete_submittable_docs(doctype, filters)
		else:
			_delete_docs(doctype, filters)

	frappe.db.delete("Comment", {"reference_doctype": "Prayer Request"})

	_delete_church_manager_user()
	frappe.db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _birthday_this_week(day_offset, birth_year):
	"""Return a birthday (as string) whose month/day falls *day_offset* days
	from today, but in *birth_year*.  This guarantees the person shows up in
	the 'Birthdays This Week' report when sample data is created."""
	target = add_days(getdate(), day_offset)
	return str(target.replace(year=birth_year))


def _near_date(day_offset):
	"""Return a date string *day_offset* days from today (negative = past)."""
	return str(add_days(getdate(), day_offset))


def _near_datetime(day_offset, time="10:00:00"):
	"""Return a datetime string *day_offset* days from today with given time."""
	return f"{_near_date(day_offset)} {time}"


def _insert_if_missing(doctype, filters, **fields):
	"""Insert a record only if it does not already exist.

	Returns the name of the existing or newly created record.
	"""
	existing = frappe.db.exists(doctype, filters)
	if existing:
		return existing

	doc = frappe.get_doc({"doctype": doctype, **fields})
	doc.insert(ignore_permissions=True)
	return doc.name


def _resolve_link(doctype, title_field, value):
	"""Look up the hash name for a record given its display value."""
	return frappe.db.get_value(doctype, {title_field: value}, "name")


def _delete_docs(doctype, filters):
	"""Delete all docs matching *filters* permanently."""
	for name in frappe.get_all(doctype, filters=filters, pluck="name"):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)


def _delete_submittable_docs(doctype, filters):
	"""Cancel and delete submittable docs matching *filters* permanently."""
	for name in frappe.get_all(doctype, filters=filters, pluck="name"):
		doc = frappe.get_doc(doctype, name)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

# Each tuple: (first, last, gender, is_member, membership_date, is_baptized,
#               baptism_date, birthday, phone, email, positions, allergies)
#
# Birthdays and position dates are computed dynamically so that reports like
# "Birthdays This Week" always have data regardless of when sample data is
# created.  The helper ``_birthday_this_week(offset, year)`` places the
# birthday *offset* days from today but in the given birth year.


def _build_people():
	"""Return the _PEOPLE list with dynamic dates."""
	return [
		(
			"James",
			"Wilson",
			"Male",
			1,
			"1990-03-12",
			1,
			"1988-07-04",
			"1962-11-08",
			"+1 202-555-0101",
			"james.wilson@example.com",
			[{"position": "Pastor", "start_date": "1995-01-01"}],
			None,
		),
		(
			"Sarah",
			"Wilson",
			"Female",
			1,
			"1991-01-20",
			1,
			"1989-04-10",
			_birthday_this_week(0, 1964),  # birthday today
			"+1 202-555-0102",
			"sarah.wilson@example.com",
			[],
			None,
		),
		(
			"Robert",
			"Johnson",
			"Male",
			1,
			"1998-09-05",
			1,
			"1997-12-25",
			"1970-07-14",
			"+1 202-555-0201",
			"robert.johnson@example.com",
			[{"position": "Elder", "start_date": "2005-01-01"}],
			None,
		),
		(
			"Mary",
			"Johnson",
			"Female",
			1,
			"1999-02-14",
			1,
			"1998-04-12",
			"1972-09-30",
			"+1 202-555-0202",
			"mary.johnson@example.com",
			[],
			"Tree nuts",
		),
		(
			"David",
			"Thompson",
			"Male",
			1,
			"2005-05-20",
			1,
			"2004-09-15",
			_birthday_this_week(2, 1980),  # birthday in 2 days
			"+1 202-555-0301",
			"david.thompson@example.com",
			[
				{"position": "Deacon", "start_date": "2010-01-01", "end_date": str(add_months(getdate(), 1))},
			],
			None,
		),
		(
			"Lisa",
			"Thompson",
			"Female",
			1,
			"2006-01-08",
			1,
			"2005-06-20",
			"1982-12-03",
			"+1 202-555-0302",
			"lisa.thompson@example.com",
			[],
			None,
		),
		(
			"Martha",
			"Evans",
			"Female",
			1,
			"2000-04-16",
			1,
			"1999-08-22",
			"1975-05-11",
			"+1 202-555-0401",
			"martha.evans@example.com",
			[
				{"position": "Secretary", "start_date": "2008-01-01"},
				{"position": "Treasurer", "start_date": "2010-01-01"},
			],
			None,
		),
		(
			"Thomas",
			"Reed",
			"Male",
			1,
			"2010-11-01",
			1,
			"2010-04-17",
			"1988-08-19",
			"+1 202-555-0501",
			"thomas.reed@example.com",
			[],
			None,
		),
		(
			"Rachel",
			"Cooper",
			"Female",
			1,
			"2015-06-22",
			1,
			"2015-01-05",
			"1992-02-28",
			"+1 202-555-0601",
			"rachel.cooper@example.com",
			[],
			"Shellfish",
		),
		(
			"Michael",
			"Grant",
			"Male",
			1,
			"2002-03-10",
			1,
			"2001-07-20",
			"1978-10-05",
			"+1 202-555-0701",
			"michael.grant@example.com",
			[],
			None,
		),
		(
			"Elizabeth",
			"Harper",
			"Female",
			1,
			"2008-08-18",
			1,
			"2007-12-25",
			_birthday_this_week(3, 1985),  # birthday in 3 days
			"+1 202-555-0801",
			"elizabeth.harper@example.com",
			[],
			None,
		),
		(
			"Samuel",
			"Brooks",
			"Male",
			0,
			None,
			0,
			None,
			"1995-06-30",
			"+1 202-555-0901",
			"samuel.brooks@example.com",
			[],
			None,
		),
	]


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

_POSITIONS = [
	"Pastor",
	"Elder",
	"Deacon",
	"Secretary",
	"Treasurer",
]


def _create_positions():
	"""Create sample Position Type records used in people data."""
	refs = {}
	for pos in _POSITIONS:
		name = _insert_if_missing(
			"Position Type",
			{"position": pos},
			position=pos,
		)
		refs[pos] = name
	return refs


def _create_people(position_refs):
	"""Create sample people and return a dict mapping 'First Last' → name."""
	# Look up hash name for "Active" membership status
	active_status = frappe.db.get_value("Member Status", {"status": "Active"}, "name")

	refs = {}
	for (
		first,
		last,
		gender,
		is_member,
		mem_date,
		is_baptized,
		bap_date,
		birthday,
		phone,
		email,
		positions,
		allergies,
	) in _build_people():
		key = f"{first} {last}"
		existing = frappe.db.get_value(
			"Person",
			{"first_name": first, "last_name": last},
			"name",
		)
		if existing:
			refs[key] = existing
			continue

		# Resolve position display names to hash names
		resolved_positions = (
			[{**p, "position": position_refs[p["position"]]} for p in positions] if positions else positions
		)

		doc = frappe.get_doc(
			{
				"doctype": "Person",
				"first_name": first,
				"last_name": last,
				"gender": gender,
				"is_member": is_member,
				"membership_date": mem_date,
				"membership_status": active_status if is_member else None,
				"is_baptized": is_baptized,
				"baptism_date": bap_date,
				"birthday": birthday,
				"primary_phone": phone,
				"email": email,
				"alergies": allergies,
				"positions": resolved_positions,
			}
		)
		doc.insert(ignore_permissions=True)
		refs[key] = doc.name
	return refs


# ---------------------------------------------------------------------------
# Church Manager user
# ---------------------------------------------------------------------------

_CHURCH_MANAGER_EMAIL = "mary.johnson@example.com"


def _create_church_manager_user(people):
	"""Create a Church Manager portal user linked to Mary Johnson."""
	if frappe.db.exists("User", _CHURCH_MANAGER_EMAIL):
		return

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": _CHURCH_MANAGER_EMAIL,
			"first_name": "Mary",
			"last_name": "Johnson",
			"send_welcome_email": 0,
			"enabled": 1,
			"role_profile_name": "Church Manager",
		}
	)
	user.insert(ignore_permissions=True)
	frappe.utils.password.update_password(_CHURCH_MANAGER_EMAIL, _CHURCH_MANAGER_EMAIL)

	person_name = people.get("Mary Johnson")
	if person_name:
		frappe.db.set_value("Person", person_name, "portal_user", _CHURCH_MANAGER_EMAIL)


def _delete_church_manager_user():
	"""Remove the sample Church Manager user."""
	if frappe.db.exists("User", _CHURCH_MANAGER_EMAIL):
		frappe.delete_doc(
			"User", _CHURCH_MANAGER_EMAIL, force=True, ignore_permissions=True, delete_permanently=True
		)


# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

_FAMILIES = [
	("Wilson - James", ["James Wilson", "Sarah Wilson"]),
	("Johnson - Robert", ["Robert Johnson", "Mary Johnson"]),
	("Thompson - David", ["David Thompson", "Lisa Thompson"]),
]

# Head of household is always the first member listed
_HEADS = {
	"Wilson - James": "James Wilson",
	"Johnson - Robert": "Robert Johnson",
	"Thompson - David": "David Thompson",
}

_SPOUSES = [
	("James Wilson", "Sarah Wilson", "1986-06-14"),
	("Robert Johnson", "Mary Johnson", "1995-10-07"),
	("David Thompson", "Lisa Thompson", "2004-08-21"),
]


def _create_families():
	"""Create sample families and return dict mapping family_name → name."""
	refs = {}
	for family_name, _ in _FAMILIES:
		existing = frappe.db.get_value("Family", {"family_name": family_name}, "name")
		if existing:
			refs[family_name] = existing
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": family_name,
			}
		)
		doc.insert(ignore_permissions=True)
		refs[family_name] = doc.name
	return refs


def _assign_families(people, families):
	"""Link people to their families and set head of household."""
	for family_name, members in _FAMILIES:
		family_doc_name = families.get(family_name)
		if not family_doc_name:
			continue
		head_key = _HEADS.get(family_name)
		for person_key in members:
			person_name = people.get(person_key)
			if not person_name:
				continue
			person = frappe.get_doc("Person", person_name)
			if person.family == family_doc_name:
				continue
			person.family = family_doc_name
			person.is_head_of_household = 1 if person_key == head_key else 0
			person.save(ignore_permissions=True)


def _assign_spouses(people):
	"""Set spouse links and marriage info for married couples."""
	for husband_key, wife_key, anniversary in _SPOUSES:
		husband_name = people.get(husband_key)
		wife_name = people.get(wife_key)
		if not husband_name or not wife_name:
			continue
		husband = frappe.get_doc("Person", husband_name)
		if husband.spouse:
			continue
		husband.is_married = 1
		husband.spouse = wife_name
		husband.anniversary = anniversary
		frappe.flags.in_import = True
		husband.save(ignore_permissions=True)
		frappe.flags.in_import = False


# ---------------------------------------------------------------------------
# Missionary Agencies
# ---------------------------------------------------------------------------

_AGENCIES = [
	{
		"agency_name": "Gospel Outreach International",
		"phone": "+1 202-555-8001",
		"email": "info@gospeloutreach.example.com",
		"website": "https://www.gospeloutreach.example.com",
		"notes": "A missions agency focused on unreached people groups in South America and Africa.",
	},
	{
		"agency_name": "Faithful Servants Mission Board",
		"phone": "+1 202-555-8002",
		"email": "contact@faithfulservants.example.com",
		"website": "https://www.faithfulservants.example.com",
		"notes": "An interdenominational mission board supporting church-planting efforts in Asia.",
	},
]


def _create_missionary_agencies():
	"""Create sample missionary agencies and return dict mapping name → name."""
	refs = {}
	for agency in _AGENCIES:
		name = _insert_if_missing("Missionary Agency", {"agency_name": agency["agency_name"]}, **agency)
		refs[agency["agency_name"]] = name
	return refs


# ---------------------------------------------------------------------------
# Missionaries
# ---------------------------------------------------------------------------


def _create_missionaries(people, agencies):
	"""Create sample missionaries."""
	monthly = _resolve_link("Missionary Support Frequency", "frequency", "Monthly")
	missionaries = [
		{
			"title": "Michael & Anna Grant",
			"person": people["Michael Grant"],
			"agency": agencies["Gospel Outreach International"],
			"country": "Brazil",
			"mission_statement": "Planting churches and training local pastors in rural communities across Brazil.",
			"publish": 1,
			"sensitive": 0,
			"support_amount": 200,
			"support_frequency": monthly,
			"support_start_date": "2010-01-01",
			"email": "michael.grant@example.com",
		},
		{
			"title": "Elizabeth Harper",
			"person": people["Elizabeth Harper"],
			"agency": agencies["Faithful Servants Mission Board"],
			"country": "Japan",
			"mission_statement": "Teaching English and sharing the Gospel at local community centers in Tokyo.",
			"publish": 1,
			"sensitive": 0,
			"support_amount": 150,
			"support_frequency": monthly,
			"support_start_date": "2012-06-01",
			"email": "elizabeth.harper@example.com",
		},
		{
			"title": "Thomas Reed",
			"person": people["Thomas Reed"],
			"agency": agencies["Gospel Outreach International"],
			"country": "Kenya",
			"mission_statement": "Providing clean water and biblical education to remote villages in Kenya.",
			"publish": 0,
			"sensitive": 1,
			"support_amount": 100,
			"support_frequency": monthly,
			"support_start_date": "2018-09-01",
			"email": "thomas.reed@example.com",
		},
	]
	for m in missionaries:
		existing = frappe.db.exists("Missionary", {"title": m["title"]})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Missionary", **m})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Funds
# ---------------------------------------------------------------------------

_FUNDS = [
	("General", "The primary operating fund for day-to-day church expenses."),
	("Missions", "Funds designated for supporting missionaries and mission trips."),
	("Building", "Savings for building maintenance, repairs, and future expansion."),
	("Benevolence", "Funds set aside to help church members and community members in need."),
]


def _create_funds():
	"""Create sample funds and return dict mapping fund name → doc name."""
	refs = {}
	for fund_name, description in _FUNDS:
		existing = frappe.db.get_value("Fund", {"fund": fund_name}, "name")
		if existing:
			refs[fund_name] = existing
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Fund",
				"fund": fund_name,
				"description": description,
			}
		)
		doc.insert(ignore_permissions=True)
		refs[fund_name] = doc.name
	return refs


# ---------------------------------------------------------------------------
# Expense Types (tree structure)
# ---------------------------------------------------------------------------


def _create_expense_types(funds):
	"""Create expense types with fund assignments.

	Returns dict mapping type name → record name.
	"""
	roots = [
		("Utilities", funds["General"], True),
		("Maintenance", funds["General"], False),
		("Office Supplies", funds["General"], False),
		("Missions Support", funds["Missions"], False),
		("Benevolence", funds["Benevolence"], False),
	]
	children = [
		("Electric", funds["General"], "Utilities"),
		("Water", funds["General"], "Utilities"),
	]

	refs = {}
	for type_name, fund, is_group in roots:
		name = _insert_if_missing(
			"Expense Type",
			{"type": type_name},
			type=type_name,
			fund=fund,
			is_group=1 if is_group else 0,
		)
		refs[type_name] = name

	for type_name, fund, parent in children:
		name = _insert_if_missing(
			"Expense Type",
			{"type": type_name},
			type=type_name,
			fund=fund,
			is_group=0,
			parent_expense_type=refs.get(parent),
		)
		refs[type_name] = name

	return refs


# ---------------------------------------------------------------------------
# Collections (submittable — saved as Draft)
# ---------------------------------------------------------------------------


def _create_collections(people, funds):
	"""Create sample collections with donations (saved as Draft)."""
	check = _resolve_link("Payment Type", "type", "Check")
	cash = _resolve_link("Payment Type", "type", "Cash")
	collections = [
		{
			"date": _near_datetime(-7, "10:30:00"),
			"notes": "Regular Sunday morning offering.",
			"expected_total": 330,
			"submit": True,
			"donations": [
				{
					"amount": 100,
					"payment_type": check,
					"fund": funds["General"],
					"person": people["James Wilson"],
					"check_number": "1001",
				},
				{
					"amount": 50,
					"payment_type": check,
					"fund": funds["Missions"],
					"person": people["James Wilson"],
					"check_number": "1001",
				},
				{
					"amount": 75,
					"payment_type": check,
					"fund": funds["General"],
					"person": people["Robert Johnson"],
					"check_number": "2001",
				},
				{
					"amount": 25,
					"payment_type": check,
					"fund": funds["Building"],
					"person": people["Robert Johnson"],
					"check_number": "2001",
				},
				{
					"amount": 50,
					"payment_type": cash,
					"fund": funds["General"],
					"person": None,
					"check_number": None,
				},
				{
					"amount": 30,
					"payment_type": check,
					"fund": funds["General"],
					"person": people["Martha Evans"],
					"check_number": "3001",
				},
			],
		},
		{
			"date": _near_datetime(0, "10:30:00"),
			"notes": "Sunday offering — missions emphasis week.",
			"expected_total": 365,
			"submit": False,
			"donations": [
				{
					"amount": 150,
					"payment_type": check,
					"fund": funds["General"],
					"person": people["James Wilson"],
					"check_number": "1002",
				},
				{
					"amount": 100,
					"payment_type": check,
					"fund": funds["Missions"],
					"person": people["David Thompson"],
					"check_number": "4001",
				},
				{
					"amount": 40,
					"payment_type": cash,
					"fund": funds["General"],
					"person": None,
					"check_number": None,
				},
				{
					"amount": 50,
					"payment_type": check,
					"fund": funds["Benevolence"],
					"person": people["Rachel Cooper"],
					"check_number": "5001",
				},
				{
					"amount": 25,
					"payment_type": cash,
					"fund": funds["Missions"],
					"person": people["Thomas Reed"],
					"check_number": None,
				},
			],
		},
	]

	for coll in collections:
		existing = frappe.db.exists("Collection", {"date": coll["date"]})
		if existing:
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Collection",
				"date": coll["date"],
				"notes": coll["notes"],
				"expected_total": coll["expected_total"],
				"donations": coll["donations"],
			}
		)
		doc.insert(ignore_permissions=True)
		if coll.get("submit"):
			doc.submit()


# ---------------------------------------------------------------------------
# Expenses (submittable — saved as Draft)
# ---------------------------------------------------------------------------


def _create_expenses(expense_types):
	"""Create sample expenses (saved as Draft)."""
	expenses = [
		{
			"type": expense_types["Electric"],
			"amount": 245.50,
			"date": _near_datetime(-5),
			"notes": "Monthly electric bill.",
		},
		{
			"type": expense_types["Water"],
			"amount": 62.00,
			"date": _near_datetime(-5),
			"notes": "Monthly water bill.",
		},
		{
			"type": expense_types["Office Supplies"],
			"amount": 89.99,
			"date": _near_datetime(-2),
			"notes": "Printer paper and toner cartridges.",
		},
	]
	for exp in expenses:
		existing = frappe.db.exists(
			"Expense",
			{
				"type": exp["type"],
				"date": exp["date"],
			},
		)
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Expense", **exp})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Prayer Requests
# ---------------------------------------------------------------------------


def _create_prayer_requests(people):
	"""Create sample prayer requests."""
	_status = {
		s: _resolve_link("Prayer Request Status", "status", s)
		for s in ("Being Prayed For", "Requested", "Answered")
	}
	_type = {
		t: _resolve_link("Prayer Request Type", "type", t)
		for t in ("Health", "Salvation", "Praise", "Unspoken")
	}
	requests = [
		{
			"title": "Pastor Wilson's Recovery",
			"status": _status["Being Prayed For"],
			"type": _type["Health"],
			"requestor": people["Sarah Wilson"],
			"recipient_type": "Person",
			"recipient": people["James Wilson"],
			"details": "Please pray for Pastor Wilson as he recovers from knee surgery. He is doing well but needs continued healing.",
			"urgent": 1,
		},
		{
			"title": "Samuel Brooks' Salvation",
			"status": _status["Requested"],
			"type": _type["Salvation"],
			"requestor": people["Rachel Cooper"],
			"recipient_type": "Person",
			"recipient": people["Samuel Brooks"],
			"details": "Please pray for Samuel, a visitor who has been attending our services. Pray that he would come to know Christ.",
			"urgent": 1,
		},
		{
			"title": "Praise: Healthy Grandson",
			"status": _status["Answered"],
			"type": _type["Praise"],
			"requestor": people["Mary Johnson"],
			"details": "Praise the Lord! Our grandson was born healthy — 7 lbs 8 oz. Mom and baby are doing great.",
		},
		{
			"title": "Unspoken Request",
			"status": _status["Being Prayed For"],
			"type": _type["Unspoken"],
			"requestor": people["Martha Evans"],
			"is_private": 1,
		},
		{
			"title": "Lisa Thompson's Medical Tests",
			"status": _status["Requested"],
			"type": _type["Health"],
			"requestor": people["Lisa Thompson"],
			"recipient_type": "Person",
			"recipient": people["Lisa Thompson"],
			"details": "Requesting prayer for upcoming medical tests next week. Trusting God for good results.",
		},
	]
	for req in requests:
		existing = frappe.db.exists(
			"Prayer Request",
			{
				"title": req["title"],
				"status": req["status"],
			},
		)
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Prayer Request", **req})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Alms Requests
# ---------------------------------------------------------------------------


def _create_alms_requests(people):
	"""Create sample alms requests."""
	requests = [
		{
			"status": "Pending",
			"recipient_type": "Person",
			"recipient": people["Samuel Brooks"],
			"requestor": people["Martha Evans"],
			"amount": 200,
			"description": "Samuel recently lost his job and is behind on his electric bill. Requesting assistance to help cover the cost.",
		},
		{
			"status": "Approved",
			"recipient_type": "Person",
			"recipient": people["Rachel Cooper"],
			"requestor": people["Rachel Cooper"],
			"amount": 150,
			"description": "Unexpected car repair needed to get to work. Requesting help with the repair bill.",
		},
	]
	for req in requests:
		existing = frappe.db.exists(
			"Alms Request",
			{
				"recipient": req["recipient"],
				"status": req["status"],
			},
		)
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Alms Request", **req})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def _create_functions():
	"""Create sample church functions."""
	_ft = {
		t: _resolve_link("Function Type", "type", t)
		for t in ("Sunday Morning Service", "Prayer Meeting", "Sunday Evening Service", "Communion")
	}
	functions = [
		{
			"function_name": "Sunday Worship",
			"type": _ft["Sunday Morning Service"],
			"start_date": _near_date(0),
			"start_time": "10:00:00",
			"end_time": "11:30:00",
			"description": "Regular Sunday morning worship service with sermon, hymns, and fellowship.",
		},
		{
			"function_name": "Midweek Prayer",
			"type": _ft["Prayer Meeting"],
			"start_date": _near_date(3),
			"start_time": "19:00:00",
			"end_time": "20:00:00",
			"description": "Weekly prayer meeting — a time to bring our requests before the Lord together.",
		},
		{
			"function_name": "Evening Service",
			"type": _ft["Sunday Evening Service"],
			"start_date": _near_date(7),
			"start_time": "18:00:00",
			"end_time": "19:30:00",
			"description": "Sunday evening service with hymns and Bible study.",
		},
		{
			"function_name": "Church Picnic",
			"type": _ft["Communion"],
			"start_date": _near_date(14),
			"all_day": 1,
			"description": "Annual church picnic at Riverside Park. Bring a dish to share!",
		},
	]
	for fn in functions:
		existing = frappe.db.exists(
			"Function",
			{
				"function_name": fn["function_name"],
				"start_date": fn["start_date"],
			},
		)
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Function", **fn})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Bible Verses
# ---------------------------------------------------------------------------

_VERSES = [
	("John", "3", "16"),
	("Psalms", "23", "1"),
	("Psalms", "23", "2"),
	("Psalms", "23", "3"),
	("Psalms", "23", "4"),
	("Psalms", "23", "5"),
	("Psalms", "23", "6"),
	("Romans", "8", "28"),
	("Philippians", "4", "13"),
	("Jeremiah", "29", "11"),
	("2 Timothy", "3", "16"),
	("Hebrews", "11", "1"),
	# Belief-related verses
	("Genesis", "1", "1"),
	("John", "1", "1"),
	("Matthew", "28", "19"),
	("Romans", "3", "23"),
	("Ephesians", "2", "8"),
	("Acts", "2", "38"),
	("1 Corinthians", "11", "26"),
	("1 Thessalonians", "4", "16"),
]


def _create_bible_verses():
	"""Create sample Bible verses and return dict mapping 'Book C:V' → name."""
	# Build lookup for Bible Book display name → hash name
	book_refs = {}
	for book_name in {b for b, _, _ in _VERSES}:
		book_refs[book_name] = frappe.db.get_value("Bible Book", {"book": book_name}, "name")

	refs = {}
	for book, chapter, verse in _VERSES:
		key = f"{book} {chapter}:{verse}"
		existing = frappe.db.get_value(
			"Bible Verse",
			{"book": book_refs[book], "chapter": chapter, "verse": verse},
			"name",
		)
		if existing:
			refs[key] = existing
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Bible Verse",
				"book": book_refs[book],
				"chapter": chapter,
				"verse": verse,
			}
		)
		doc.insert(ignore_permissions=True)
		refs[key] = doc.name
	return refs


# ---------------------------------------------------------------------------
# Bible References
# ---------------------------------------------------------------------------


def _create_bible_references(verses):
	"""Create sample Bible references."""
	_tr = {
		t: _resolve_link("Bible Translation", "translation", t)
		for t in (
			"King James Version",
			"English Standard Version",
			"New International Version",
			"New King James Version",
		)
	}
	references = [
		{
			"start_verse": verses["John 3:16"],
			"translation": _tr["King James Version"],
			"reference_text": (
				"For God so loved the world, that he gave his only begotten Son, "
				"that whosoever believeth in him should not perish, but have "
				"everlasting life."
			),
		},
		{
			"start_verse": verses["Romans 8:28"],
			"translation": _tr["English Standard Version"],
			"reference_text": (
				"And we know that for those who love God all things work together "
				"for good, for those who are called according to his purpose."
			),
		},
		{
			"start_verse": verses["Psalms 23:1"],
			"end_verse": verses["Psalms 23:6"],
			"translation": _tr["King James Version"],
			"reference_text": (
				"The LORD is my shepherd; I shall not want. He maketh me to lie "
				"down in green pastures: he leadeth me beside the still waters. "
				"He restoreth my soul: he leadeth me in the paths of righteousness "
				"for his name's sake. Yea, though I walk through the valley of the "
				"shadow of death, I will fear no evil: for thou art with me; thy rod "
				"and thy staff they comfort me. Thou preparest a table before me in "
				"the presence of mine enemies: thou anointest my head with oil; my "
				"cup runneth over. Surely goodness and mercy shall follow me all the "
				"days of my life: and I will dwell in the house of the LORD for ever."
			),
		},
		{
			"start_verse": verses["Jeremiah 29:11"],
			"translation": _tr["New International Version"],
			"reference_text": (
				"For I know the plans I have for you, declares the LORD, plans to "
				"prosper you and not to harm you, plans to give you hope and a future."
			),
		},
		{
			"start_verse": verses["Philippians 4:13"],
			"translation": _tr["New King James Version"],
			"reference_text": ("I can do all things through Christ who strengthens me."),
		},
	]
	# Belief-supporting references (no text — just verse pointers)
	belief_refs = [
		{"start_verse": verses["Genesis 1:1"]},
		{"start_verse": verses["John 1:1"]},
		{"start_verse": verses["2 Timothy 3:16"]},
		{"start_verse": verses["Matthew 28:19"]},
		{"start_verse": verses["Romans 3:23"]},
		{"start_verse": verses["Ephesians 2:8"]},
		{"start_verse": verses["Acts 2:38"]},
		{"start_verse": verses["1 Corinthians 11:26"]},
		{"start_verse": verses["1 Thessalonians 4:16"]},
	]
	references += belief_refs

	for ref in references:
		# Bible Reference names are auto-generated by script
		existing = frappe.db.exists(
			"Bible Reference",
			{
				"start_verse": ref["start_verse"],
				"translation": ref.get("translation"),
			},
		)
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Bible Reference", **ref})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Sermons
# ---------------------------------------------------------------------------


def _create_sermons(people):
	"""Create sample sermons."""
	sermons = [
		{
			"title": "The Good Shepherd",
			"prepared_by": people["James Wilson"],
			"publish": 1,
			"notes": (
				"<p>A sermon on Psalm 23 exploring the intimate care that God, "
				"our Shepherd, provides for His sheep.</p>"
				"<h3>Outline</h3>"
				"<ol>"
				"<li>The Shepherd's Provision (vv. 1-3)</li>"
				"<li>The Shepherd's Protection (v. 4)</li>"
				"<li>The Shepherd's Promise (vv. 5-6)</li>"
				"</ol>"
			),
		},
		{
			"title": "Walking by Faith",
			"prepared_by": people["James Wilson"],
			"publish": 1,
			"notes": (
				"<p>A study of Hebrews 11:1 and what it means to walk by faith "
				"rather than by sight in our daily lives.</p>"
				"<h3>Key Points</h3>"
				"<ul>"
				"<li>Faith defined: substance and evidence</li>"
				"<li>Examples from the hall of faith</li>"
				"<li>Applying faith to modern challenges</li>"
				"</ul>"
			),
		},
		{
			"title": "The Power of Prayer",
			"prepared_by": people["Robert Johnson"],
			"publish": 1,
			"notes": (
				"<p>An encouraging message on the privilege and power of prayer, "
				"drawing from multiple passages throughout Scripture.</p>"
				"<h3>Points</h3>"
				"<ol>"
				"<li>Prayer as communion with God</li>"
				"<li>Prayer as a weapon in spiritual warfare</li>"
				"<li>Prayer as a means of transformation</li>"
				"</ol>"
			),
		},
	]
	for sermon in sermons:
		existing = frappe.db.exists("Sermon", {"title": sermon["title"]})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Sermon", **sermon})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Beliefs
# ---------------------------------------------------------------------------


def _create_beliefs(verses):
	"""Create sample belief statements for the church website."""
	beliefs = [
		{
			"title": "The Bible",
			"belief_statement": (
				"<p>We believe the Bible is the inspired, infallible, and authoritative "
				"Word of God. It is sufficient for all matters of faith and practice, "
				"and is the final authority for the life of the believer.</p>"
			),
			"publish": 1,
			"bible_references": ["2 Timothy 3:16"],
		},
		{
			"title": "God",
			"belief_statement": (
				"<p>We believe in one God, eternally existing in three persons: "
				"Father, Son, and Holy Spirit. He is the Creator of all things, "
				"infinite in power, wisdom, and love.</p>"
			),
			"publish": 1,
			"bible_references": ["Genesis 1:1", "John 1:1", "Matthew 28:19"],
		},
		{
			"title": "Salvation",
			"belief_statement": (
				"<p>We believe that all have sinned and fall short of the glory of God. "
				"Salvation is a gift of God's grace, received through faith in Jesus "
				"Christ alone, and not by works.</p>"
			),
			"publish": 1,
			"bible_references": ["Romans 3:23", "Ephesians 2:8", "John 3:16"],
		},
		{
			"title": "Baptism",
			"belief_statement": (
				"<p>We believe that baptism by immersion is an act of obedience "
				"symbolizing the believer's identification with Christ in His death, "
				"burial, and resurrection.</p>"
			),
			"publish": 1,
			"bible_references": ["Acts 2:38"],
		},
		{
			"title": "The Lord's Supper",
			"belief_statement": (
				"<p>We believe the Lord's Supper is an ordinance given by Christ to "
				"His church as a memorial of His sacrifice. It is to be observed "
				"regularly until He comes again.</p>"
			),
			"publish": 1,
			"bible_references": ["1 Corinthians 11:26"],
		},
		{
			"title": "The Return of Christ",
			"belief_statement": (
				"<p>We believe in the personal, visible, and bodily return of the "
				"Lord Jesus Christ. This blessed hope has a purifying effect on "
				"the life of the believer.</p>"
			),
			"publish": 1,
			"bible_references": ["1 Thessalonians 4:16"],
		},
	]

	for belief in beliefs:
		if frappe.db.exists("Belief", {"title": belief["title"]}):
			continue

		# Resolve Bible Reference names from start_verse display key
		ref_rows = []
		for verse_key in belief.pop("bible_references", []):
			verse_hash = verses.get(verse_key)
			if not verse_hash:
				continue
			ref_name = frappe.db.get_value(
				"Bible Reference",
				{"start_verse": verse_hash},
				"name",
			)
			if ref_name:
				ref_rows.append({"reference": ref_name})

		doc = frappe.get_doc(
			{
				"doctype": "Belief",
				"bible_references": ref_rows,
				**belief,
			}
		)
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Group Roles (supporting data for Groups)
# ---------------------------------------------------------------------------


def _get_group_role_refs():
	"""Return dict mapping role → name for roles created by after_install."""
	return {role: frappe.db.get_value("Group Role", {"role": role}, "name") for role in ("Leader", "Member")}


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


def _create_groups(people, group_roles):
	"""Create sample groups with members. Returns dict mapping group_name → name."""
	groups = [
		{
			"group_name": "Worship Team",
			"description": "Musicians and singers who lead the congregation in worship each Sunday.",
			"members": [
				{"person": people["James Wilson"], "group_role": group_roles["Leader"]},
				{"person": people["Rachel Cooper"], "group_role": group_roles["Member"]},
				{"person": people["Thomas Reed"], "group_role": group_roles["Member"]},
			],
		},
		{
			"group_name": "Men's Bible Study",
			"description": "A weekly men's group studying through the book of Romans.",
			"members": [
				{"person": people["Robert Johnson"], "group_role": group_roles["Leader"]},
				{"person": people["David Thompson"], "group_role": group_roles["Member"]},
				{"person": people["Michael Grant"], "group_role": group_roles["Member"]},
			],
		},
		{
			"group_name": "Building Committee",
			"description": "Oversees building maintenance, repairs, and future expansion projects.",
			"members": [
				{"person": people["David Thompson"], "group_role": group_roles["Leader"]},
				{"person": people["Martha Evans"], "group_role": group_roles["Member"]},
			],
		},
	]
	refs = {}
	for grp in groups:
		existing = frappe.db.get_value(
			"Group",
			{"group_name": grp["group_name"]},
			"name",
		)
		if existing:
			refs[grp["group_name"]] = existing
			continue
		doc = frappe.get_doc({"doctype": "Group", **grp})
		doc.insert(ignore_permissions=True)
		refs[grp["group_name"]] = doc.name
	return refs


# ---------------------------------------------------------------------------
# Ministries
# ---------------------------------------------------------------------------


def _create_ministries(groups):
	"""Create sample ministries, optionally linked to groups."""
	ministries = [
		{
			"ministry_name": "Worship Ministry",
			"description": "Leading the congregation in musical worship.",
			"group": groups.get("Worship Team"),
			"start_date": "2020-01-05",
			"publish": 1,
		},
		{
			"ministry_name": "Men's Ministry",
			"description": "Equipping men to grow in faith through Bible study and fellowship.",
			"group": groups.get("Men's Bible Study"),
			"start_date": "2021-09-12",
			"publish": 1,
		},
		{
			"ministry_name": "Facilities Ministry",
			"description": "Maintaining and improving the church building and grounds.",
			"group": groups.get("Building Committee"),
			"start_date": "2018-06-01",
		},
	]
	for ministry in ministries:
		_insert_if_missing(
			"Ministry",
			{"ministry_name": ministry["ministry_name"]},
			**ministry,
		)


# ---------------------------------------------------------------------------
# Fund Transfers (submittable — saved as Draft)
# ---------------------------------------------------------------------------


def _create_fund_transfers(funds):
	"""Create sample fund transfers (saved as Draft)."""
	transfers = [
		{
			"from_fund": funds["General"],
			"to_fund": funds["Building"],
			"amount": 500,
			"date": _near_datetime(-3),
			"notes": "Quarterly transfer to building maintenance reserve.",
		},
		{
			"from_fund": funds["General"],
			"to_fund": funds["Benevolence"],
			"amount": 200,
			"date": _near_datetime(-7),
			"notes": "Monthly benevolence fund allocation.",
		},
	]
	for xfer in transfers:
		existing = frappe.db.exists(
			"Fund Transfer",
			{
				"from_fund": xfer["from_fund"],
				"to_fund": xfer["to_fund"],
				"date": xfer["date"],
			},
		)
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Fund Transfer", **xfer})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Prayers
# ---------------------------------------------------------------------------


def _create_prayers(people):
	"""Create sample prayers with topics linking to existing Prayer Requests."""
	# Look up Prayer Request names by their unique attributes
	# type field stores hash names, so resolve first
	_prt = {
		t: _resolve_link("Prayer Request Type", "type", t) for t in ("Health", "Salvation", "Praise")
	}
	pr_wilson = frappe.db.get_value(
		"Prayer Request",
		{"requestor": people["Sarah Wilson"], "type": _prt["Health"]},
		"name",
	)
	pr_samuel = frappe.db.get_value(
		"Prayer Request",
		{"requestor": people["Rachel Cooper"], "type": _prt["Salvation"]},
		"name",
	)
	pr_praise = frappe.db.get_value(
		"Prayer Request",
		{"requestor": people["Mary Johnson"], "type": _prt["Praise"]},
		"name",
	)

	prayers = [
		{
			"person": people["James Wilson"],
			"content": (
				"Heavenly Father, we come before You this Lord's Day morning with "
				"grateful hearts. We lift up those among us who are hurting — those "
				"facing illness, loss, and uncertainty. Grant them Your peace and "
				"healing. We pray for Samuel, that You would draw him to Yourself. "
				"In Jesus' name, Amen."
			),
			"topics": [
				{
					"topic_type": "Prayer Request",
					"topic": pr_wilson,
					"prayer": "Prayed for Pastor Wilson's recovery from knee surgery.",
				},
				{
					"topic_type": "Prayer Request",
					"topic": pr_samuel,
					"prayer": "Prayed for Samuel Brooks' salvation.",
				},
			],
		},
		{
			"person": people["Robert Johnson"],
			"content": (
				"Lord, we gather midweek to seek Your face. We thank You for "
				"answered prayers — for the safe arrival of the Johnsons' grandson. "
				"We ask for Your guidance as our church considers the building "
				"expansion project. Give wisdom to the committee and provide the "
				"resources according to Your will. Amen."
			),
			"topics": [
				{
					"topic_type": "Prayer Request",
					"topic": pr_praise,
					"prayer": "Gave thanks for the answered prayer — healthy grandson.",
				},
			],
		},
	]

	for pr in prayers:
		existing = frappe.db.exists(
			"Prayer",
			{
				"person": pr["person"],
			},
		)
		if existing:
			continue

		# Filter out topics where the Prayer Request wasn't found
		topics = [t for t in pr.pop("topics") if t.get("topic")]

		doc = frappe.get_doc(
			{
				"doctype": "Prayer",
				"topics": topics,
				**pr,
			}
		)
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Songs
# ---------------------------------------------------------------------------


def _create_songs():
	"""Create sample songs with lyric slides."""
	songs = [
		{
			"title": "Amazing Grace",
			"ccli": "4755360",
			"slides": [
				{
					"content": "<p>Amazing grace! How sweet the sound<br>That saved a wretch like me!<br>I once was lost, but now am found;<br>Was blind, but now I see.</p>"
				},
				{
					"content": "<p>'Twas grace that taught my heart to fear,<br>And grace my fears relieved;<br>How precious did that grace appear<br>The hour I first believed.</p>"
				},
				{
					"content": "<p>Through many dangers, toils, and snares,<br>I have already come;<br>'Tis grace hath brought me safe thus far,<br>And grace will lead me home.</p>"
				},
			],
		},
		{
			"title": "How Great Thou Art",
			"ccli": "14181",
			"slides": [
				{
					"content": "<p>O Lord my God, when I in awesome wonder<br>Consider all the worlds Thy hands have made,<br>I see the stars, I hear the rolling thunder,<br>Thy power throughout the universe displayed.</p>"
				},
				{
					"content": "<p>Then sings my soul, my Saviour God, to Thee:<br>How great Thou art! How great Thou art!<br>Then sings my soul, my Saviour God, to Thee:<br>How great Thou art! How great Thou art!</p>"
				},
			],
		},
		{
			"title": "Holy, Holy, Holy",
			"ccli": "1156",
			"slides": [
				{
					"content": "<p>Holy, holy, holy! Lord God Almighty!<br>Early in the morning our song shall rise to Thee;<br>Holy, holy, holy, merciful and mighty!<br>God in three Persons, blessed Trinity!</p>"
				},
				{
					"content": "<p>Holy, holy, holy! All the saints adore Thee,<br>Casting down their golden crowns around the glassy sea;<br>Cherubim and seraphim falling down before Thee,<br>Who wert, and art, and evermore shalt be.</p>"
				},
			],
		},
	]
	for song in songs:
		existing = frappe.db.exists("Song", {"title": song["title"]})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Song", **song})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

_LOCATIONS = [
	# (name, parent_key, is_group)
	("Main Campus", None, True),
	("Sanctuary", "Main Campus", False),
	("Fellowship Hall", "Main Campus", False),
	("Kitchen", "Main Campus", False),
	("Parking Lot", "Main Campus", False),
]


def _create_locations():
	"""Create sample locations in tree order. Returns dict mapping label → name."""
	refs = {}
	for label, parent_key, is_group in _LOCATIONS:
		existing = frappe.db.get_value("Location", {"location_name": label}, "name")
		if existing:
			refs[label] = existing
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Location",
				"location_name": label,
				"is_group": 1 if is_group else 0,
				"parent_location": refs.get(parent_key),
			}
		)
		doc.insert(ignore_permissions=True)
		refs[label] = doc.name
	return refs


# ---------------------------------------------------------------------------
# Church Assets
# ---------------------------------------------------------------------------


def _create_church_assets(locations):
	"""Create sample church assets linked to locations."""
	assets = [
		{
			"title": "Yamaha Grand Piano",
			"acquisition_date": "2010-03-15",
			"location": locations.get("Sanctuary"),
			"notes": "<p>Yamaha C3X grand piano. Tuned twice yearly by Davidson Piano Services.</p>",
		},
		{
			"title": "Epson Projector",
			"acquisition_date": "2020-08-10",
			"location": locations.get("Fellowship Hall"),
			"notes": "<p>Epson PowerLite projector used for presentations and movie nights.</p>",
		},
		{
			"title": "Commercial Refrigerator",
			"acquisition_date": "2015-01-20",
			"location": locations.get("Kitchen"),
			"notes": "<p>True brand two-door commercial refrigerator for church dinners and events.</p>",
		},
		{
			"title": "15-Passenger Van",
			"acquisition_date": "2018-06-01",
			"location": locations.get("Parking Lot"),
			"notes": "<p>Ford Transit 15-passenger van used for youth trips and senior outings.</p>",
		},
	]
	for asset in assets:
		existing = frappe.db.exists("Church Asset", {"title": asset["title"]})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Church Asset", **asset})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Church Tasks (tree structure)
# ---------------------------------------------------------------------------


def _create_church_tasks(people):
	"""Create sample church tasks with hierarchy."""
	# Parent task (is_group)
	parent_title = "Prepare for Upcoming Service"
	parent_name = frappe.db.get_value(
		"Church Task",
		{"title": parent_title},
		"name",
	)
	if not parent_name:
		parent_doc = frappe.get_doc(
			{
				"doctype": "Church Task",
				"title": parent_title,
				"status": "In Progress",
				"due_date": _near_datetime(7),
				"assigned_person": people["James Wilson"],
				"is_group": 1,
				"notes": "<p>Everything that needs to be done before next week's service.</p>",
			}
		)
		parent_doc.insert(ignore_permissions=True)
		parent_name = parent_doc.name

	# Sub-tasks
	sub_tasks = [
		{
			"title": "Set up candles and holders",
			"status": "Assigned",
			"due_date": _near_datetime(6, "17:00:00"),
			"assigned_person": people["David Thompson"],
			"notes": "<p>Place candles and drip guards on every pew. Extra supplies are in the storage closet.</p>",
		},
		{
			"title": "Prepare song slides",
			"status": "In Progress",
			"due_date": _near_datetime(5, "12:00:00"),
			"assigned_person": people["Rachel Cooper"],
			"notes": "<p>Create presentation slides for Silent Night, O Holy Night, and Joy to the World.</p>",
		},
	]
	for task in sub_tasks:
		existing = frappe.db.exists(
			"Church Task",
			{
				"title": task["title"],
			},
		)
		if existing:
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Church Task",
				"parent_task": parent_name,
				**task,
			}
		)
		doc.insert(ignore_permissions=True)

	# Standalone tasks
	standalone_tasks = [
		{
			"title": "Fix Fellowship Hall sink",
			"status": "In Progress",
			"due_date": _near_datetime(3),
			"assigned_person": people["David Thompson"],
			"notes": "<p>The faucet in the Fellowship Hall kitchen is leaking. Parts have been ordered from the hardware store.</p>",
		},
		{
			"title": "Order new hymnals",
			"status": "Open",
			"due_date": _near_datetime(30),
			"assigned_person": people["Martha Evans"],
			"notes": "<p>We need 25 additional hymnals for the new pew section. Get quotes from at least two suppliers.</p>",
		},
	]
	for task in standalone_tasks:
		existing = frappe.db.exists(
			"Church Task",
			{
				"title": task["title"],
			},
		)
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Church Task", **task})
		doc.insert(ignore_permissions=True)
