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

	Creates sample data when the user opts in during setup.
	"""
	if args and args.get("create_sample_data"):
		create_sample_data()


@frappe.whitelist()
def create():
	"""Whitelisted method to create sample data from the browser console.

	Usage:  frappe.call("church.setup.sample_data.create")
	"""
	create_sample_data()
	frappe.msgprint("Sample data has been created.", indicator="green", alert=True)


@frappe.whitelist()
def delete():
	"""Whitelisted method to remove sample data.

	Usage:  frappe.call("church.setup.sample_data.delete")
	"""
	delete_sample_data()
	frappe.msgprint("Sample data has been removed.", indicator="green", alert=True)


def create_sample_data():
	"""Create all sample data in dependency order."""
	church = _create_church()

	people = _create_people(church)

	families = _create_families(church)
	_assign_families(people, families)
	_assign_spouses(people)

	agencies = _create_missionary_agencies()
	_create_missionaries(church, people, agencies)

	funds = _create_funds(church)
	expense_types = _create_expense_types(funds)

	_create_collections(church, people, funds)
	_create_expenses(church, expense_types)

	_create_prayer_requests(church, people)
	_create_alms_requests(church, people)

	_create_functions(church)

	verses = _create_bible_verses(church)
	_create_bible_references(verses, church)

	_create_beliefs(church)

	_create_sermons(church, people, funds)

	frappe.db.commit()


def delete_sample_data():
	"""Remove all sample data created by :func:`create_sample_data`."""
	church = CHURCH_NAME

	_delete_docs("Belief", {"church": church})
	_delete_docs("Sermon", {"church": church})
	_delete_docs("Bible Reference", {"church": church})
	_delete_docs("Bible Verse", {"church": church})
	_delete_docs("Function", {"church": church})
	_delete_docs("Alms Request", {"church": church})
	_delete_docs("Prayer Request", {"church": church})
	_delete_submittable_docs("Expense", {"church": church})
	_delete_docs("Expense Type", {})
	_delete_submittable_docs("Collection", {"church": church})
	_delete_docs("Fund", {"church": church})
	_delete_docs("Missionary", {"church": church})
	_delete_docs("Missionary Agency", {})
	_delete_docs("Family", {"church": church})
	_delete_docs("Person", {"church": church})
	_delete_docs("Church", {"church_name": church})

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


# ---------------------------------------------------------------------------
# Church
# ---------------------------------------------------------------------------

CHURCH_NAME = "Grace Community Church"


def _create_church():
	"""Create a single sample church."""
	_insert_if_missing(
		"Church",
		CHURCH_NAME,
		church_name=CHURCH_NAME,
		legal_name="Grace Community Church, Inc.",
		founding_date="1985-06-15",
		default_bible_translation="King James Version",
		mission_statement=(
			"To glorify God by making disciples of all nations through the faithful "
			"preaching of His Word, the fellowship of believers, and compassionate "
			"service to our community and the world."
		),
		about=(
			"<p>Grace Community Church was founded in 1985 by a small group of "
			"families committed to biblical teaching and community outreach. Over the "
			"years, we have grown into a vibrant congregation that values faithful "
			"exposition of Scripture, heartfelt worship, and genuine fellowship.</p>"
			"<p>We are an independent, non-denominational church committed to the "
			"authority of the Bible and the sufficiency of Christ.</p>"
		),
	)
	return CHURCH_NAME


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


def _create_missionary_agencies():
	"""Create sample missionary agencies and return dict mapping name → name."""
	refs = {}
	for agency in _AGENCIES:
		name = _insert_if_missing("Missionary Agency", agency["agency_name"], **agency)
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


def _create_expense_types(funds):
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
			type=type_name, fund=fund, is_group=1 if type_name == "Utilities" else 0,
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
			type=type_name, fund=fund, parent_expense_type=parent,
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
# Events / Functions
# ---------------------------------------------------------------------------


def _create_functions(church):
	"""Create sample church events."""
	events = [
		{
			"event_name": "Sunday Worship",
			"type": "Sunday Morning Service",
			"start_date": "2025-12-01",
			"start_time": "10:00:00",
			"end_time": "11:30:00",
			"description": "Regular Sunday morning worship service with sermon, hymns, and fellowship.",
		},
		{
			"event_name": "Midweek Prayer",
			"type": "Prayer Meeting",
			"start_date": "2025-12-03",
			"start_time": "19:00:00",
			"end_time": "20:00:00",
			"description": "Weekly prayer meeting — a time to bring our requests before the Lord together.",
		},
		{
			"event_name": "Christmas Eve Service",
			"type": "Sunday Evening Service",
			"start_date": "2025-12-24",
			"start_time": "18:00:00",
			"end_time": "19:30:00",
			"description": "A candlelight service celebrating the birth of our Lord Jesus Christ.",
		},
		{
			"event_name": "Church Picnic",
			"type": "Communion",
			"start_date": "2025-09-06",
			"all_day": 1,
			"description": "Annual church picnic at Riverside Park. Bring a dish to share!",
		},
	]
	for ev in events:
		existing = frappe.db.exists("Function", {
			"church": church, "event_name": ev["event_name"], "start_date": ev["start_date"],
		})
		if existing:
			continue
		doc = frappe.get_doc({"doctype": "Function", "church": church, **ev})
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


def _create_sermons(church, people, funds):
	"""Create sample sermons with slides linking to Person, Fund, and Belief records."""
	# Look up Fund doc names by fund label
	general_fund = funds["General"]
	missions_fund = funds["Missions"]

	sermons = [
		{
			"title": "The Good Shepherd",
			"prepared_by": people["James Wilson"],
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
			"slides": [
				{
					"slide_type": "Person",
					"slide": people["James Wilson"],
					"notes": "<p>Pastor James Wilson — preaching on Psalm 23.</p>",
				},
				{
					"slide_type": "Belief",
					"slide": "The Bible",
					"notes": "<p>Our statement of faith regarding the authority of Scripture.</p>",
				},
				{
					"slide_type": "Fund",
					"slide": general_fund,
					"notes": "<p>Please consider giving to the General Fund to support ongoing ministry.</p>",
				},
			],
		},
		{
			"title": "Walking by Faith",
			"prepared_by": people["James Wilson"],
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
			"slides": [
				{
					"slide_type": "Person",
					"slide": people["Robert Johnson"],
					"notes": "<p>Elder Robert Johnson — reading from Hebrews 11.</p>",
				},
				{
					"slide_type": "Belief",
					"slide": "Salvation",
					"notes": "<p>What we believe about salvation by grace through faith.</p>",
				},
				{
					"slide_type": "Fund",
					"slide": missions_fund,
					"notes": "<p>Support our missionaries who walk by faith around the world.</p>",
				},
			],
		},
		{
			"title": "The Power of Prayer",
			"prepared_by": people["Robert Johnson"],
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
			"slides": [
				{
					"slide_type": "Person",
					"slide": people["Martha Evans"],
					"notes": "<p>Sister Martha Evans — sharing a testimony on answered prayer.</p>",
				},
				{
					"slide_type": "Belief",
					"slide": "God",
					"notes": "<p>We believe in one God — the One to whom we direct our prayers.</p>",
				},
				{
					"slide_type": "Fund",
					"slide": general_fund,
					"notes": "<p>Your tithes and offerings keep this ministry running.</p>",
				},
			],
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
