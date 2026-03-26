"""
Sample data for the Church app.

Creates a realistic set of sample records so new users can explore the app
immediately after installation.  Intended to be called from the setup wizard
when the user opts in to sample data.

All inserts are idempotent — safe to run more than once on the same site.
"""

import frappe


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def setup_wizard_complete(args):
	"""Hook called by Frappe's setup wizard on completion.

	Runs the full after_install setup (church, lookups, website content,
	etc.) using the church name from the ERPNext organization slide, then
	optionally creates sample data.
	"""
	from church.patches.after_wizard import execute as after_install

	after_install(args)

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
	church = _get_church()

	people = _create_people(church)
	_create_church_manager_user(church, people)

	families = _create_families(church)
	_assign_families(people, families)
	_assign_spouses(people)

	agencies = _create_missionary_agencies(church)
	_create_missionaries(church, people, agencies)

	funds = _create_funds(church)
	expense_types = _create_expense_types(church, funds)

	_create_collections(church, people, funds)
	_create_expenses(church, expense_types)

	_create_prayer_requests(church, people)
	_create_alms_requests(church, people)

	_create_functions(church)

	verses = _create_bible_verses(church)
	_create_bible_references(verses, church)

	_create_sermons(church, people)

	_create_beliefs(church)

	group_types = _create_group_types(church)
	group_roles = _create_group_roles(church)
	_create_groups(church, people, group_types, group_roles)

	_create_fund_transfers(church, funds)

	_create_prayers(church, people)

	_create_songs(church)

	# Assets, Projects, and Tasks depend on an ERPNext Company existing
	# (created by the ERPNext setup wizard).  Skip if the wizard hasn't run.
	company = frappe.db.get_value("Company", {}, "name")
	if company:
		_create_locations()
		_create_asset_items()
		_create_assets(church, company)

		_create_projects(church, company)
		_create_tasks(church, people)

	frappe.db.commit()


def delete_sample_data():
	"""Remove all sample data created by :func:`create_sample_data`."""
	church = _get_church()

	_delete_docs("Task", {"church": church})
	_delete_submittable_docs("Asset", {"church": church})
	_delete_docs("Project", {"church": church})
	_delete_sample_items_and_locations()
	_delete_docs("Song", {"church": church})
	_delete_docs("Prayer", {"church": church})
	_delete_submittable_docs("Fund Transfer", {"church": church})
	_delete_docs("Group", {"church": church})
	_delete_docs("Group Role", {"church": church})
	_delete_docs("Group Type", {"church": church})
	_delete_docs("Belief", {"church": church})
	_delete_docs("Sermon", {"church": church})
	_delete_docs("Bible Reference", {"church": church})
	_delete_docs("Bible Verse", {"church": church})
	_delete_docs("Function", {"church": church})
	_delete_docs("Alms Request", {"church": church})
	_delete_docs("Prayer Request", {"church": church})
	_delete_submittable_docs("Expense", {"church": church})
	_delete_docs("Expense Type", {"church": church})
	_delete_submittable_docs("Collection", {"church": church})
	_delete_docs("Fund", {"church": church})
	_delete_docs("Missionary", {"church": church})
	_delete_docs("Missionary Agency", {"church": church})
	_delete_docs("Family", {"church": church})
	_delete_church_manager_user()
	_delete_docs("Person", {"church": church})

	frappe.db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _delete_docs(doctype, filters):
	"""Delete all docs matching *filters*."""
	for name in frappe.get_all(doctype, filters=filters, pluck="name"):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def _delete_submittable_docs(doctype, filters):
	"""Cancel and delete submittable docs matching *filters*."""
	for name in frappe.get_all(doctype, filters=filters, pluck="name"):
		doc = frappe.get_doc(doctype, name)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def _delete_sample_items_and_locations():
	"""Delete sample Items and Locations created for asset categorization."""
	sample_items = ["Equipment", "Vehicle", "Furniture", "Musical Instrument", "Electronics"]
	for item in sample_items:
		if frappe.db.exists("Item", item):
			frappe.delete_doc("Item", item, force=True, ignore_permissions=True)

	sample_locations = ["Sanctuary", "Fellowship Hall", "Kitchen", "Office", "Parking Lot", "Storage"]
	for loc in sample_locations:
		if frappe.db.exists("Location", loc):
			frappe.delete_doc("Location", loc, force=True, ignore_permissions=True)

	if frappe.db.exists("Asset Category", "Church Assets"):
		frappe.delete_doc("Asset Category", "Church Assets", force=True, ignore_permissions=True)


def _get_church():
	"""Return the root church name from the database."""
	root = frappe.db.get_value(
		"Church", {"parent_church": ("is", "not set")}, "name"
	)
	if not root:
		frappe.throw("No church found. Please complete the setup wizard first.")
	return root


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

# Each tuple: (first, last, gender, is_member, membership_date, is_baptized,
#               baptism_date, birthday, phone, email, positions, allergies)
_PEOPLE = [
	("James", "Wilson", "Male", 1, "1990-03-12", 1, "1988-07-04", "1962-11-08",
	 "+1 202-555-0101", "james.wilson@example.com",
	 [{"position": "Pastor", "start_date": "1995-01-01"}],
	 None),
	("Sarah", "Wilson", "Female", 1, "1991-01-20", 1, "1989-04-10", "1964-03-22",
	 "+1 202-555-0102", "sarah.wilson@example.com", [], None),
	("Robert", "Johnson", "Male", 1, "1998-09-05", 1, "1997-12-25", "1970-07-14",
	 "+1 202-555-0201", "robert.johnson@example.com",
	 [{"position": "Elder", "start_date": "2005-01-01"}],
	 None),
	("Mary", "Johnson", "Female", 1, "1999-02-14", 1, "1998-04-12", "1972-09-30",
	 "+1 202-555-0202", "mary.johnson@example.com", [], "Tree nuts"),
	("David", "Thompson", "Male", 1, "2005-05-20", 1, "2004-09-15", "1980-01-25",
	 "+1 202-555-0301", "david.thompson@example.com",
	 [{"position": "Deacon", "start_date": "2010-01-01"}],
	 None),
	("Lisa", "Thompson", "Female", 1, "2006-01-08", 1, "2005-06-20", "1982-12-03",
	 "+1 202-555-0302", "lisa.thompson@example.com", [], None),
	("Martha", "Evans", "Female", 1, "2000-04-16", 1, "1999-08-22", "1975-05-11",
	 "+1 202-555-0401", "martha.evans@example.com",
	 [{"position": "Secretary", "start_date": "2008-01-01"},
	  {"position": "Treasurer", "start_date": "2010-01-01"}],
	 None),
	("Thomas", "Reed", "Male", 1, "2010-11-01", 1, "2010-04-17", "1988-08-19",
	 "+1 202-555-0501", "thomas.reed@example.com", [], None),
	("Rachel", "Cooper", "Female", 1, "2015-06-22", 1, "2015-01-05", "1992-02-28",
	 "+1 202-555-0601", "rachel.cooper@example.com", [], "Shellfish"),
	("Michael", "Grant", "Male", 1, "2002-03-10", 1, "2001-07-20", "1978-10-05",
	 "+1 202-555-0701", "michael.grant@example.com", [], None),
	("Elizabeth", "Harper", "Female", 1, "2008-08-18", 1, "2007-12-25", "1985-04-17",
	 "+1 202-555-0801", "elizabeth.harper@example.com", [], None),
	("Samuel", "Brooks", "Male", 0, None, 0, None, "1995-06-30",
	 "+1 202-555-0901", "samuel.brooks@example.com", [], None),
]


def _create_people(church):
	"""Create sample people and return a dict mapping 'First Last' → name."""
	refs = {}
	for (first, last, gender, is_member, mem_date, is_baptized, bap_date,
	     birthday, phone, email, positions, allergies) in _PEOPLE:
		key = f"{first} {last}"
		existing = frappe.db.get_value(
			"Person",
			{"church": church, "first_name": first, "last_name": last},
			"name",
		)
		if existing:
			refs[key] = existing
			continue

		doc = frappe.get_doc({
			"doctype": "Person",
			"church": church,
			"first_name": first,
			"last_name": last,
			"gender": gender,
			"is_member": is_member,
			"membership_date": mem_date,
			"membership_status": "Active" if is_member else None,
			"is_baptized": is_baptized,
			"baptism_date": bap_date,
			"birthday": birthday,
			"primary_phone": phone,
			"email": email,
			"alergies": allergies,
			"positions": positions,
		})
		doc.insert(ignore_permissions=True)
		refs[key] = doc.name
	return refs


# ---------------------------------------------------------------------------
# Church Manager user
# ---------------------------------------------------------------------------

_CHURCH_MANAGER_EMAIL = "mary.johnson@example.com"


def _create_church_manager_user(church, people):
	"""Create a Church Manager portal user linked to Mary Johnson."""
	if frappe.db.exists("User", _CHURCH_MANAGER_EMAIL):
		return

	user = frappe.get_doc({
		"doctype": "User",
		"email": _CHURCH_MANAGER_EMAIL,
		"first_name": "Mary",
		"last_name": "Johnson",
		"send_welcome_email": 0,
		"enabled": 1,
		"role_profile_name": "Church Manager",
		"church": church,
	})
	user.insert(ignore_permissions=True)
	frappe.utils.password.update_password(_CHURCH_MANAGER_EMAIL, _CHURCH_MANAGER_EMAIL)

	person_name = people.get("Mary Johnson")
	if person_name:
		frappe.db.set_value("Person", person_name, "portal_user", _CHURCH_MANAGER_EMAIL)


def _delete_church_manager_user():
	"""Remove the sample Church Manager user."""
	if frappe.db.exists("User", _CHURCH_MANAGER_EMAIL):
		frappe.delete_doc("User", _CHURCH_MANAGER_EMAIL, force=True, ignore_permissions=True)


# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

_FAMILIES = [
	("Wilson - James", ["James Wilson", "Sarah Wilson"]),
	("Johnson - Robert", ["Robert Johnson", "Mary Johnson"]),
	("Thompson - David", ["David Thompson", "Lisa Thompson"]),
]

# Head of household is always the first member listed
_HEADS = {"Wilson - James": "James Wilson",
           "Johnson - Robert": "Robert Johnson",
           "Thompson - David": "David Thompson"}

_SPOUSES = [
	("James Wilson", "Sarah Wilson", "1986-06-14"),
	("Robert Johnson", "Mary Johnson", "1995-10-07"),
	("David Thompson", "Lisa Thompson", "2004-08-21"),
]


def _create_families(church):
	"""Create sample families and return dict mapping family_name → name."""
	refs = {}
	for family_name, _ in _FAMILIES:
		existing = frappe.db.get_value("Family", {"church": church, "family_name": family_name}, "name")
		if existing:
			refs[family_name] = existing
			continue

		doc = frappe.get_doc({
			"doctype": "Family",
			"church": church,
			"family_name": family_name,
		})
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
		husband.save(ignore_permissions=True)


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


def _create_missionary_agencies(church):
	"""Create sample missionary agencies and return dict mapping name → name."""
	refs = {}
	for agency in _AGENCIES:
		name = _insert_if_missing("Missionary Agency", agency["agency_name"], church=church, **agency)
		refs[agency["agency_name"]] = name
	return refs


# ---------------------------------------------------------------------------
# Missionaries
# ---------------------------------------------------------------------------


def _create_missionaries(church, people, agencies):
	"""Create sample missionaries."""
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
			"support_frequency": "Monthly",
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
			"support_frequency": "Monthly",
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
			"support_frequency": "Monthly",
			"support_start_date": "2018-09-01",
			"email": "thomas.reed@example.com",
		},
	]
	for m in missionaries:
		existing = frappe.db.exists("Missionary", {"title": m["title"]})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Missionary", "church": church, **m})
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


def _create_funds(church):
	"""Create sample funds and return dict mapping fund name → doc name."""
	refs = {}
	for fund_name, description in _FUNDS:
		existing = frappe.db.get_value("Fund", {"church": church, "fund": fund_name}, "name")
		if existing:
			refs[fund_name] = existing
			continue
		doc = frappe.get_doc({
			"doctype": "Fund",
			"church": church,
			"fund": fund_name,
			"description": description,
		})
		doc.insert(ignore_permissions=True)
		refs[fund_name] = doc.name
	return refs


# ---------------------------------------------------------------------------
# Expense Types (tree structure)
# ---------------------------------------------------------------------------


def _create_expense_types(church, funds):
	"""Create sample expense types and return dict mapping type → name."""
	refs = {}

	# Root-level types
	roots = [
		("Utilities", funds["General"]),
		("Maintenance", funds["General"]),
		("Office Supplies", funds["General"]),
		("Missions Support", funds["Missions"]),
		("Benevolence", funds["Benevolence"]),
	]
	for type_name, fund in roots:
		name = _insert_if_missing(
			"Expense Type", type_name,
			church=church, type=type_name, fund=fund, is_group=1 if type_name == "Utilities" else 0,
		)
		refs[type_name] = name

	# Children of Utilities
	children = [
		("Electric", funds["General"], "Utilities"),
		("Water", funds["General"], "Utilities"),
	]
	for type_name, fund, parent in children:
		name = _insert_if_missing(
			"Expense Type", type_name,
			church=church, type=type_name, fund=fund, parent_expense_type=parent,
		)
		refs[type_name] = name

	return refs


# ---------------------------------------------------------------------------
# Collections (submittable — saved as Draft)
# ---------------------------------------------------------------------------


def _create_collections(church, people, funds):
	"""Create sample collections with donations (saved as Draft)."""
	collections = [
		{
			"date": "2025-12-01 10:30:00",
			"notes": "Regular Sunday morning offering.",
			"donations": [
				{"amount": 100, "payment_type": "Check", "fund": funds["General"],
				 "person": people["James Wilson"], "check_number": "1001"},
				{"amount": 50, "payment_type": "Check", "fund": funds["Missions"],
				 "person": people["James Wilson"], "check_number": "1001"},
				{"amount": 75, "payment_type": "Check", "fund": funds["General"],
				 "person": people["Robert Johnson"], "check_number": "2001"},
				{"amount": 25, "payment_type": "Check", "fund": funds["Building"],
				 "person": people["Robert Johnson"], "check_number": "2001"},
				{"amount": 50, "payment_type": "Cash", "fund": funds["General"],
				 "person": None, "check_number": None},
				{"amount": 30, "payment_type": "Check", "fund": funds["General"],
				 "person": people["Martha Evans"], "check_number": "3001"},
			],
		},
		{
			"date": "2025-12-08 10:30:00",
			"notes": "Sunday offering — missions emphasis week.",
			"donations": [
				{"amount": 150, "payment_type": "Check", "fund": funds["General"],
				 "person": people["James Wilson"], "check_number": "1002"},
				{"amount": 100, "payment_type": "Check", "fund": funds["Missions"],
				 "person": people["David Thompson"], "check_number": "4001"},
				{"amount": 40, "payment_type": "Cash", "fund": funds["General"],
				 "person": None, "check_number": None},
				{"amount": 50, "payment_type": "Check", "fund": funds["Benevolence"],
				 "person": people["Rachel Cooper"], "check_number": "5001"},
				{"amount": 25, "payment_type": "Cash", "fund": funds["Missions"],
				 "person": people["Thomas Reed"], "check_number": None},
			],
		},
	]

	for coll in collections:
		existing = frappe.db.exists("Collection", {"church": church, "date": coll["date"]})
		if existing:
			continue
		doc = frappe.get_doc({
			"doctype": "Collection",
			"church": church,
			"date": coll["date"],
			"notes": coll["notes"],
			"donations": coll["donations"],
		})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Expenses (submittable — saved as Draft)
# ---------------------------------------------------------------------------


def _create_expenses(church, expense_types):
	"""Create sample expenses (saved as Draft)."""
	expenses = [
		{"type": expense_types["Electric"], "amount": 245.50,
		 "date": "2025-12-05 00:00:00", "notes": "December electric bill."},
		{"type": expense_types["Water"], "amount": 62.00,
		 "date": "2025-12-05 00:00:00", "notes": "December water bill."},
		{"type": expense_types["Office Supplies"], "amount": 89.99,
		 "date": "2025-12-10 00:00:00", "notes": "Printer paper and toner cartridges."},
	]
	for exp in expenses:
		existing = frappe.db.exists("Expense", {
			"church": church, "type": exp["type"], "date": exp["date"],
		})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Expense", "church": church, **exp})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Prayer Requests
# ---------------------------------------------------------------------------


def _create_prayer_requests(church, people):
	"""Create sample prayer requests."""
	requests = [
		{
			"status": "Being Prayed For",
			"type": "Health",
			"requestor": people["Sarah Wilson"],
			"recipient_type": "Person",
			"recipient": people["James Wilson"],
			"request": "Please pray for Pastor Wilson as he recovers from knee surgery. He is doing well but needs continued healing.",
		},
		{
			"status": "Requested",
			"type": "Salvation",
			"requestor": people["Rachel Cooper"],
			"recipient_type": "Person",
			"recipient": people["Samuel Brooks"],
			"request": "Please pray for Samuel, a visitor who has been attending our services. Pray that he would come to know Christ.",
		},
		{
			"status": "Answered",
			"type": "Praise",
			"requestor": people["Mary Johnson"],
			"request": "Praise the Lord! Our grandson was born healthy — 7 lbs 8 oz. Mom and baby are doing great.",
		},
		{
			"status": "Being Prayed For",
			"type": "Unspoken",
			"requestor": people["Martha Evans"],
			"is_private": 1,
		},
		{
			"status": "Requested",
			"type": "Health",
			"requestor": people["Lisa Thompson"],
			"recipient_type": "Person",
			"recipient": people["Lisa Thompson"],
			"request": "Requesting prayer for upcoming medical tests next week. Trusting God for good results.",
		},
	]
	for req in requests:
		existing = frappe.db.exists("Prayer Request", {
			"church": church, "requestor": req["requestor"],
			"type": req["type"], "status": req["status"],
		})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Prayer Request", "church": church, **req})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Alms Requests
# ---------------------------------------------------------------------------


def _create_alms_requests(church, people):
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
		existing = frappe.db.exists("Alms Request", {
			"church": church, "recipient": req["recipient"], "status": req["status"],
		})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Alms Request", "church": church, **req})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def _create_functions(church):
	"""Create sample church functions."""
	functions = [
		{
			"function_name": "Sunday Worship",
			"type": "Sunday Morning Service",
			"start_date": "2025-12-01",
			"start_time": "10:00:00",
			"end_time": "11:30:00",
			"description": "Regular Sunday morning worship service with sermon, hymns, and fellowship.",
		},
		{
			"function_name": "Midweek Prayer",
			"type": "Prayer Meeting",
			"start_date": "2025-12-03",
			"start_time": "19:00:00",
			"end_time": "20:00:00",
			"description": "Weekly prayer meeting — a time to bring our requests before the Lord together.",
		},
		{
			"function_name": "Christmas Eve Service",
			"type": "Sunday Evening Service",
			"start_date": "2025-12-24",
			"start_time": "18:00:00",
			"end_time": "19:30:00",
			"description": "A candlelight service celebrating the birth of our Lord Jesus Christ.",
		},
		{
			"function_name": "Church Picnic",
			"type": "Communion",
			"start_date": "2025-09-06",
			"all_day": 1,
			"description": "Annual church picnic at Riverside Park. Bring a dish to share!",
		},
	]
	for fn in functions:
		existing = frappe.db.exists("Function", {
			"church": church, "function_name": fn["function_name"], "start_date": fn["start_date"],
		})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Function", "church": church, **fn})
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


def _create_bible_verses(church):
	"""Create sample Bible verses and return dict mapping 'Book C:V' → name."""
	refs = {}
	for book, chapter, verse in _VERSES:
		key = f"{book} {chapter}:{verse}"
		existing = frappe.db.exists("Bible Verse", key)
		if existing:
			refs[key] = existing
			continue
		doc = frappe.get_doc({
			"doctype": "Bible Verse",
			"church": church,
			"book": book,
			"chapter": chapter,
			"verse": verse,
		})
		doc.insert(ignore_permissions=True)
		refs[key] = doc.name
	return refs


# ---------------------------------------------------------------------------
# Bible References
# ---------------------------------------------------------------------------


def _create_bible_references(verses, church):
	"""Create sample Bible references."""
	references = [
		{
			"start_verse": verses["John 3:16"],
			"translation": "King James Version",
			"reference_text": (
				"For God so loved the world, that he gave his only begotten Son, "
				"that whosoever believeth in him should not perish, but have "
				"everlasting life."
			),
		},
		{
			"start_verse": verses["Romans 8:28"],
			"translation": "English Standard Version",
			"reference_text": (
				"And we know that for those who love God all things work together "
				"for good, for those who are called according to his purpose."
			),
		},
		{
			"start_verse": verses["Psalms 23:1"],
			"end_verse": verses["Psalms 23:6"],
			"translation": "King James Version",
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
			"translation": "New International Version",
			"reference_text": (
				"For I know the plans I have for you, declares the LORD, plans to "
				"prosper you and not to harm you, plans to give you hope and a future."
			),
		},
		{
			"start_verse": verses["Philippians 4:13"],
			"translation": "New King James Version",
			"reference_text": (
				"I can do all things through Christ who strengthens me."
			),
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
		existing = frappe.db.exists("Bible Reference", {
			"start_verse": ref["start_verse"],
			"translation": ref.get("translation"),
		})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Bible Reference", "church": church, **ref})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Sermons
# ---------------------------------------------------------------------------


def _create_sermons(church, people):
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
		existing = frappe.db.exists("Sermon", sermon["title"])
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Sermon", "church": church, **sermon})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Beliefs
# ---------------------------------------------------------------------------


def _create_beliefs(church):
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
		if frappe.db.exists("Belief", belief["title"]):
			continue

		# Resolve Bible Reference names from start_verse
		ref_rows = []
		for verse_name in belief.pop("bible_references", []):
			# Find the Bible Reference doc whose start_verse matches
			ref_name = frappe.db.get_value(
				"Bible Reference", {"start_verse": verse_name}, "name",
			)
			if ref_name:
				ref_rows.append({"reference": ref_name})

		doc = frappe.get_doc({
			"doctype": "Belief",
			"church": church,
			"bible_references": ref_rows,
			**belief,
		})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Group Types & Group Roles (supporting data for Groups)
# ---------------------------------------------------------------------------


def _create_group_types(church):
	"""Create sample group types and return dict mapping type → name."""
	refs = {}
	for type_name in ("Ministry", "Small Group", "Committee"):
		name = _insert_if_missing("Group Type", type_name, church=church, type=type_name)
		refs[type_name] = name
	return refs


def _create_group_roles(church):
	"""Create sample group roles and return dict mapping role → name."""
	refs = {}
	for role_name in ("Leader", "Member"):
		name = _insert_if_missing("Group Role", role_name, church=church, role=role_name)
		refs[role_name] = name
	return refs


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


def _create_groups(church, people, group_types, group_roles):
	"""Create sample groups with members."""
	groups = [
		{
			"group_name": "Worship Team",
			"group_type": group_types["Ministry"],
			"description": "Musicians and singers who lead the congregation in worship each Sunday.",
			"members": [
				{"person": people["James Wilson"], "group_role": group_roles["Leader"]},
				{"person": people["Rachel Cooper"], "group_role": group_roles["Member"]},
				{"person": people["Thomas Reed"], "group_role": group_roles["Member"]},
			],
		},
		{
			"group_name": "Men's Bible Study",
			"group_type": group_types["Small Group"],
			"description": "A weekly men's group studying through the book of Romans.",
			"members": [
				{"person": people["Robert Johnson"], "group_role": group_roles["Leader"]},
				{"person": people["David Thompson"], "group_role": group_roles["Member"]},
				{"person": people["Michael Grant"], "group_role": group_roles["Member"]},
			],
		},
		{
			"group_name": "Building Committee",
			"group_type": group_types["Committee"],
			"description": "Oversees building maintenance, repairs, and future expansion projects.",
			"members": [
				{"person": people["David Thompson"], "group_role": group_roles["Leader"]},
				{"person": people["Martha Evans"], "group_role": group_roles["Member"]},
			],
		},
	]
	for grp in groups:
		existing = frappe.db.get_value(
			"Group", {"church": church, "group_name": grp["group_name"]}, "name",
		)
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Group", "church": church, **grp})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Fund Transfers (submittable — saved as Draft)
# ---------------------------------------------------------------------------


def _create_fund_transfers(church, funds):
	"""Create sample fund transfers (saved as Draft)."""
	transfers = [
		{
			"from_fund": funds["General"],
			"to_fund": funds["Building"],
			"amount": 500,
			"date": "2025-12-15 00:00:00",
			"notes": "Quarterly transfer to building maintenance reserve.",
		},
		{
			"from_fund": funds["General"],
			"to_fund": funds["Benevolence"],
			"amount": 200,
			"date": "2025-12-01 00:00:00",
			"notes": "Monthly benevolence fund allocation.",
		},
	]
	for xfer in transfers:
		existing = frappe.db.exists("Fund Transfer", {
			"church": church, "from_fund": xfer["from_fund"],
			"to_fund": xfer["to_fund"], "date": xfer["date"],
		})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Fund Transfer", "church": church, **xfer})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Prayers
# ---------------------------------------------------------------------------


def _create_prayers(church, people):
	"""Create sample prayers with topics linking to existing Prayer Requests."""
	# Look up Prayer Request names by their unique attributes
	pr_wilson = frappe.db.get_value(
		"Prayer Request", {"church": church, "requestor": people["Sarah Wilson"], "type": "Health"}, "name",
	)
	pr_samuel = frappe.db.get_value(
		"Prayer Request", {"church": church, "requestor": people["Rachel Cooper"], "type": "Salvation"}, "name",
	)
	pr_praise = frappe.db.get_value(
		"Prayer Request", {"church": church, "requestor": people["Mary Johnson"], "type": "Praise"}, "name",
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
				{"topic_type": "Prayer Request", "topic": pr_wilson,
				 "prayer": "Prayed for Pastor Wilson's recovery from knee surgery."},
				{"topic_type": "Prayer Request", "topic": pr_samuel,
				 "prayer": "Prayed for Samuel Brooks' salvation."},
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
				{"topic_type": "Prayer Request", "topic": pr_praise,
				 "prayer": "Gave thanks for the answered prayer — healthy grandson."},
			],
		},
	]

	for pr in prayers:
		existing = frappe.db.exists("Prayer", {
			"church": church, "person": pr["person"],
		})
		if existing:
			continue

		# Filter out topics where the Prayer Request wasn't found
		topics = [t for t in pr.pop("topics") if t.get("topic")]

		doc = frappe.get_doc({
			"doctype": "Prayer",
			"church": church,
			"topics": topics,
			**pr,
		})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Songs
# ---------------------------------------------------------------------------


def _create_songs(church):
	"""Create sample songs with lyric slides."""
	songs = [
		{
			"title": "Amazing Grace",
			"ccli": "4755360",
			"slides": [
				{"content": "<p>Amazing grace! How sweet the sound<br>That saved a wretch like me!<br>I once was lost, but now am found;<br>Was blind, but now I see.</p>"},
				{"content": "<p>'Twas grace that taught my heart to fear,<br>And grace my fears relieved;<br>How precious did that grace appear<br>The hour I first believed.</p>"},
				{"content": "<p>Through many dangers, toils, and snares,<br>I have already come;<br>'Tis grace hath brought me safe thus far,<br>And grace will lead me home.</p>"},
			],
		},
		{
			"title": "How Great Thou Art",
			"ccli": "14181",
			"slides": [
				{"content": "<p>O Lord my God, when I in awesome wonder<br>Consider all the worlds Thy hands have made,<br>I see the stars, I hear the rolling thunder,<br>Thy power throughout the universe displayed.</p>"},
				{"content": "<p>Then sings my soul, my Saviour God, to Thee:<br>How great Thou art! How great Thou art!<br>Then sings my soul, my Saviour God, to Thee:<br>How great Thou art! How great Thou art!</p>"},
			],
		},
		{
			"title": "Holy, Holy, Holy",
			"ccli": "1156",
			"slides": [
				{"content": "<p>Holy, holy, holy! Lord God Almighty!<br>Early in the morning our song shall rise to Thee;<br>Holy, holy, holy, merciful and mighty!<br>God in three Persons, blessed Trinity!</p>"},
				{"content": "<p>Holy, holy, holy! All the saints adore Thee,<br>Casting down their golden crowns around the glassy sea;<br>Cherubim and seraphim falling down before Thee,<br>Who wert, and art, and evermore shalt be.</p>"},
			],
		},
	]
	for song in songs:
		existing = frappe.db.exists("Song", {"church": church, "title": song["title"]})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Song", "church": church, **song})
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Locations (ERPNext Location doctype, used by Asset)
# ---------------------------------------------------------------------------


def _create_locations():
	"""Create sample locations for asset tracking."""
	locations = ["Sanctuary", "Fellowship Hall", "Kitchen", "Office", "Parking Lot", "Storage"]
	for loc in locations:
		if not frappe.db.exists("Location", loc):
			frappe.get_doc({"doctype": "Location", "location_name": loc}).insert(
				ignore_permissions=True,
			)


# ---------------------------------------------------------------------------
# Asset Items (ERPNext Item doctype with is_fixed_asset=1)
# ---------------------------------------------------------------------------


def _create_asset_items():
	"""Create sample fixed-asset Items for asset categorization."""
	if not frappe.db.exists("Asset Category", "Church Assets"):
		frappe.get_doc({"doctype": "Asset Category", "asset_category_name": "Church Assets"}).insert(
			ignore_permissions=True, ignore_mandatory=True,
		)

	items = ["Equipment", "Vehicle", "Furniture", "Musical Instrument", "Electronics"]
	for item in items:
		if not frappe.db.exists("Item", item):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item,
					"item_name": item,
					"item_group": "All Item Groups",
					"is_fixed_asset": 1,
					"is_stock_item": 0,
					"asset_category": "Church Assets",
				}
			).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Assets (ERPNext Asset doctype)
# ---------------------------------------------------------------------------


def _create_assets(church, company):
	"""Create sample assets using the ERPNext Asset doctype."""
	assets = [
		{
			"asset_name": "Yamaha Grand Piano",
			"item_code": "Musical Instrument",
			"location": "Sanctuary",
			"purchase_date": "2010-03-15",
			"gross_purchase_amount": 25000,
		},
		{
			"asset_name": "Epson Projector",
			"item_code": "Electronics",
			"location": "Fellowship Hall",
			"purchase_date": "2020-08-10",
			"gross_purchase_amount": 800,
		},
		{
			"asset_name": "Commercial Refrigerator",
			"item_code": "Equipment",
			"location": "Kitchen",
			"purchase_date": "2015-01-20",
			"gross_purchase_amount": 3500,
		},
		{
			"asset_name": "15-Passenger Van",
			"item_code": "Vehicle",
			"location": "Parking Lot",
			"purchase_date": "2018-06-01",
			"gross_purchase_amount": 35000,
		},
	]
	for asset in assets:
		if frappe.db.exists("Asset", {"church": church, "asset_name": asset["asset_name"]}):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Asset",
				"church": church,
				"company": company,
				**asset,
			}
		)
		doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Projects (ERPNext Project doctype)
# ---------------------------------------------------------------------------


def _create_projects(church, company):
	"""Create sample projects."""
	if frappe.db.exists("Project", {"church": church, "project_name": "Christmas Eve Service"}):
		return
	frappe.get_doc(
		{
			"doctype": "Project",
			"church": church,
			"company": company,
			"project_name": "Christmas Eve Service",
			"status": "Open",
			"expected_start_date": "2025-12-01",
			"expected_end_date": "2025-12-24",
			"notes": "<p>Plan and execute the annual Christmas Eve candlelight service.</p>",
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Tasks (ERPNext Task doctype, tree structure)
# ---------------------------------------------------------------------------


def _create_tasks(church, people):
	"""Create sample tasks with hierarchy using the ERPNext Task doctype."""
	# Parent task (is_group)
	parent_subject = "Prepare for Christmas Eve Service"
	parent_name = frappe.db.get_value(
		"Task", {"church": church, "subject": parent_subject}, "name",
	)
	if not parent_name:
		parent_doc = frappe.get_doc(
			{
				"doctype": "Task",
				"church": church,
				"subject": parent_subject,
				"status": "Working",
				"exp_end_date": "2025-12-24",
				"is_group": 1,
				"description": "<p>Everything that needs to be done before the Christmas Eve candlelight service.</p>",
			}
		)
		parent_doc.insert(ignore_permissions=True)
		parent_name = parent_doc.name

	# Sub-tasks
	sub_tasks = [
		{
			"subject": "Set up candles and holders",
			"status": "Open",
			"exp_end_date": "2025-12-23",
			"description": "<p>Place candles and drip guards on every pew. Extra supplies are in the storage closet.</p>",
		},
		{
			"subject": "Prepare song slides",
			"status": "Working",
			"exp_end_date": "2025-12-22",
			"description": "<p>Create presentation slides for Silent Night, O Holy Night, and Joy to the World.</p>",
		},
	]
	for task in sub_tasks:
		if frappe.db.exists("Task", {"church": church, "subject": task["subject"]}):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Task",
				"church": church,
				"parent_task": parent_name,
				**task,
			}
		)
		doc.insert(ignore_permissions=True)

	# Standalone tasks
	standalone_tasks = [
		{
			"subject": "Fix Fellowship Hall sink",
			"status": "Working",
			"exp_end_date": "2025-12-20",
			"description": "<p>The faucet in the Fellowship Hall kitchen is leaking. Parts have been ordered from the hardware store.</p>",
		},
		{
			"subject": "Order new hymnals",
			"status": "Open",
			"exp_end_date": "2026-01-15",
			"description": "<p>We need 25 additional hymnals for the new pew section. Get quotes from at least two suppliers.</p>",
		},
	]
	for task in standalone_tasks:
		if frappe.db.exists("Task", {"church": church, "subject": task["subject"]}):
			continue
		doc = frappe.get_doc({"doctype": "Task", "church": church, **task})
		doc.insert(ignore_permissions=True)
