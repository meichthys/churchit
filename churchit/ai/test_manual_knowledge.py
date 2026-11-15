# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The manuals as Flow knowledge: the sections, when churchit queues the sync, and what a sync changes.

The sync tests run only on a Frappe with Flow and never call an embedding model: Flow's reading of a
source is patched by dotted path.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.html_utils import has_html_tags

from churchit.ai import manual_knowledge
from churchit.ai.manual_knowledge import (
	KNOWLEDGE_BASE,
	SYNC_JOB,
	get_manual_sections,
	queue_sync,
	split_sections,
)
from churchit.ai.switch import SETTINGS, has_flow
from churchit.manuals import get_manuals
from churchit.tests.helpers import RollbackEachTest, ensure_user

CHURCH_MANAGER = "_test_manual_knowledge_manager@example.com"
SETTINGS_DOCTYPE = "Flow Knowledge Settings"
EMBEDDING_MODEL = "_Test Manual Embedding Model"
# Flow's reading of a source, which sends it to the embedding model, and the removal of its chunks.
INGEST = "frappe.flow.knowledge.ingest.ingest_source"
PURGE = "frappe.flow.knowledge.ingest.purge_source"
AGENT_SYNC_JOB = "churchit.ai.flow.sync_agents"
SECTIONS = [
	{"title": "Manual: Test > One", "content": "Manual: Test > One\n\nThe first section."},
	{"title": "Manual: Test > Two", "content": "Manual: Test > Two\n\nThe second section."},
	{"title": "Manual: Test > Three", "content": "Manual: Test > Three\n\nThe third section."},
]


def set_ai(enabled: int) -> None:
	frappe.db.set_single_value(SETTINGS, "enabled", enabled)


def set_embedding_model(model: str | None) -> None:
	frappe.db.set_single_value(SETTINGS_DOCTYPE, "embedding_model", model)
	frappe.clear_document_cache(SETTINGS_DOCTYPE, SETTINGS_DOCTYPE)


def queued_jobs(enqueue) -> list[str]:
	return [call.kwargs["job_id"] for call in enqueue.call_args_list]


class TestManualSections(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.sections = get_manual_sections()

	def test_every_manual_gives_sections(self):
		manuals = {manual["name"] for manual in get_manuals()}

		self.assertEqual(
			{section["title"].split(" > ")[0].split(" (")[0] for section in self.sections}, manuals
		)

	def test_each_section_is_plain_text(self):
		for section in self.sections:
			self.assertFalse(has_html_tags(section["content"]), section["title"])
			self.assertNotIn("&nbsp;", section["content"], section["title"])
			self.assertTrue(section["content"].startswith(section["title"]))

	def test_titles_are_unique_because_the_sync_matches_sources_by_title(self):
		titles = [section["title"] for section in self.sections]

		self.assertEqual(len(titles), len(set(titles)))

	def test_a_title_links_the_manuals_desk_page(self):
		people = [
			section["title"] for section in self.sections if section["title"].startswith("Manual: People")
		]

		self.assertTrue(people)
		for title in people:
			self.assertTrue(title.endswith("(/desk/manual:-people)"), title)

	def test_a_section_runs_from_its_heading_to_the_next(self):
		blocks = [
			{"type": "paragraph", "data": {"text": '<span class="h1">Test Manual</span>'}},
			{"type": "paragraph", "data": {"text": "The intro."}},
			{"type": "paragraph", "data": {"text": '<span class="h2">🧭Pathways</span>'}},
			{
				"type": "paragraph",
				"data": {
					"text": 'Open <a href="/app/pathway">Pathways</a>.<br>Then&nbsp;add one &amp; save.'
				},
			},
			{"type": "list", "data": {"style": "unordered", "items": ["<b>One</b>", "Two"]}},
			{"type": "card", "data": {"card_name": "Not text"}},
			{"type": "header", "data": {"text": "<b>Next</b>", "level": 3}},
			{"type": "paragraph", "data": {"text": "Open https://&lt;your site&gt;/calendar."}},
		]

		self.assertEqual(
			split_sections(blocks),
			[
				(None, ["The intro."]),
				("🧭Pathways", ["Open Pathways.\nThen add one & save.", "- One", "- Two"]),
				("Next", ["Open https://&lt;your site&gt;/calendar."]),
			],
		)


class TestQueueSync(RollbackEachTest):
	"""queue_sync after migrate and when AI is turned on: one job, only when the sync can run."""

	def setUp(self):
		super().setUp()
		set_ai(1)
		if has_flow():
			self.addCleanup(frappe.clear_document_cache, SETTINGS_DOCTYPE, SETTINGS_DOCTYPE)
			frappe.get_doc(
				{
					"doctype": "Flow Model",
					"name": EMBEDDING_MODEL,
					"title": EMBEDDING_MODEL,
					"model_id": "ollama/_test",
					"embedding": 1,
					"enabled": 1,
				}
			).db_insert()
			set_embedding_model(EMBEDDING_MODEL)

	def queued(self) -> list[str]:
		with patch("frappe.enqueue") as enqueue:
			queue_sync()
		return queued_jobs(enqueue)

	def test_nothing_is_queued_while_ai_is_off(self):
		set_ai(0)

		self.assertEqual(self.queued(), [])

	def test_nothing_is_queued_without_flow(self):
		with patch.object(manual_knowledge, "has_flow", return_value=False):
			self.assertEqual(self.queued(), [])

	def test_nothing_is_queued_without_an_enabled_embedding_model(self):
		if not has_flow():
			self.skipTest("This Frappe has no Flow.")

		frappe.db.set_value("Flow Model", EMBEDDING_MODEL, "enabled", 0)
		self.assertEqual(self.queued(), [])

		set_embedding_model(None)
		self.assertEqual(self.queued(), [])

	def test_one_job_is_queued_once_with_ai_on_and_an_embedding_model(self):
		if not has_flow():
			self.skipTest("This Frappe has no Flow.")

		with patch("frappe.enqueue") as enqueue:
			queue_sync()

		enqueue.assert_called_once_with(
			SYNC_JOB, queue="long", job_id=SYNC_JOB, deduplicate=True, enqueue_after_commit=True
		)

	def test_turning_ai_on_queues_the_agent_and_manual_syncs(self):
		set_ai(0)
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		settings = frappe.get_single(SETTINGS)
		settings.update({"enabled": 1, "acknowledged": 1})

		with patch("frappe.enqueue") as enqueue:
			settings.save()
			settings.save()

		self.assertEqual(queued_jobs(enqueue), [AGENT_SYNC_JOB, SYNC_JOB] if has_flow() else [])


class TestManualSync(RollbackEachTest):
	"""sync_manual_knowledge: one Text source per section, and only changed sections read again."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.church_manager = ensure_user(CHURCH_MANAGER, "Manual Manager", roles=("Church Manager",))

	def setUp(self):
		if not has_flow():
			self.skipTest("This Frappe has no Flow.")
		super().setUp()
		from churchit.ai import flow

		self.flow = flow
		self.addCleanup(frappe.clear_document_cache, SETTINGS_DOCTYPE, SETTINGS_DOCTYPE)
		set_ai(1)
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)
		frappe.get_doc(
			{
				"doctype": "Flow Model",
				"name": EMBEDDING_MODEL,
				"title": EMBEDDING_MODEL,
				"model_id": "ollama/_test",
				"embedding": 1,
				"enabled": 1,
			}
		).db_insert()
		set_embedding_model(EMBEDDING_MODEL)
		for source in frappe.get_all(
			"Flow Knowledge Source", {"knowledge_base": KNOWLEDGE_BASE}, pluck="name"
		):
			frappe.db.delete("Flow Knowledge Source", source)
		frappe.db.delete("Flow Knowledge Base", KNOWLEDGE_BASE)
		self.sections = [dict(section) for section in SECTIONS]
		self.ingest = self.enterContext(patch(INGEST, side_effect=self.mark_read))
		self.enterContext(patch(PURGE))

	def mark_read(self, source: str, rebuild: bool = False) -> None:
		frappe.db.set_value("Flow Knowledge Source", source, "status", "Completed")

	def sync(self) -> None:
		with patch.object(manual_knowledge, "get_manual_sections", return_value=self.sections):
			self.flow.sync_manual_knowledge()

	def get_sources(self) -> dict[str, str]:
		"""Each source of the knowledge base, title: name."""
		return dict(
			frappe.get_all(
				"Flow Knowledge Source", {"knowledge_base": KNOWLEDGE_BASE}, ["title", "name"], as_list=True
			)
		)

	def test_the_first_sync_adds_one_text_source_per_section(self):
		self.sync()

		sources = frappe.get_all(
			"Flow Knowledge Source",
			{"knowledge_base": KNOWLEDGE_BASE},
			["title", "content", "source_type", "owner"],
			order_by="creation",
		)
		self.assertEqual(
			[(source.title, source.content) for source in sources],
			[(s["title"], s["content"]) for s in SECTIONS],
		)
		self.assertEqual({source.source_type for source in sources}, {"Text"})
		self.assertEqual({source.owner for source in sources}, {"Administrator"})
		self.assertEqual(self.ingest.call_count, len(SECTIONS))

	def test_a_second_sync_with_no_change_adds_nothing(self):
		self.sync()
		before = self.get_sources()
		self.ingest.reset_mock()

		self.sync()

		self.ingest.assert_not_called()
		self.assertEqual(self.get_sources(), before)

	def test_a_second_sync_of_the_real_manuals_adds_nothing(self):
		"""Each saved source keeps its text through Frappe's XSS filter, tag-like text such as
		<your site> included, so the sync matches it."""
		self.flow.sync_manual_knowledge()
		self.ingest.reset_mock()

		self.flow.sync_manual_knowledge()

		self.ingest.assert_not_called()

	def test_a_changed_section_replaces_only_its_source(self):
		self.sync()
		before = self.get_sources()
		self.ingest.reset_mock()

		self.sections[1]["content"] += " Changed."
		self.sync()

		after = self.get_sources()
		self.assertEqual(self.ingest.call_count, 1)
		self.assertNotEqual(after["Manual: Test > Two"], before["Manual: Test > Two"])
		self.assertFalse(frappe.db.exists("Flow Knowledge Source", before["Manual: Test > Two"]))
		for title in ("Manual: Test > One", "Manual: Test > Three"):
			self.assertEqual(after[title], before[title])

	def test_a_section_that_is_gone_loses_its_source(self):
		self.sync()
		gone = self.get_sources()["Manual: Test > Three"]

		del self.sections[2]
		self.sync()

		self.assertEqual(set(self.get_sources()), {"Manual: Test > One", "Manual: Test > Two"})
		self.assertFalse(frappe.db.exists("Flow Knowledge Source", gone))

	def test_a_source_that_flow_could_not_read_is_added_again(self):
		self.sync()
		failed = self.get_sources()["Manual: Test > One"]
		frappe.db.set_value("Flow Knowledge Source", failed, "status", "Failed")
		self.ingest.reset_mock()

		self.sync()

		self.assertEqual(self.ingest.call_count, 1)
		self.assertFalse(frappe.db.exists("Flow Knowledge Source", failed))

	def test_the_sync_does_nothing_while_ai_is_off(self):
		set_ai(0)

		self.sync()

		self.assertFalse(frappe.db.exists("Flow Knowledge Base", KNOWLEDGE_BASE))

	def test_the_sync_does_nothing_without_an_enabled_embedding_model(self):
		frappe.db.set_value("Flow Model", EMBEDDING_MODEL, "enabled", 0)

		self.sync()

		self.assertFalse(frappe.db.exists("Flow Knowledge Base", KNOWLEDGE_BASE))

	def test_the_sync_runs_as_administrator_and_gives_the_user_back(self):
		frappe.set_user(self.church_manager)

		self.sync()

		self.assertEqual(frappe.session.user, self.church_manager)
		frappe.set_user("Administrator")
		self.assertEqual(len(self.get_sources()), len(SECTIONS))

	def test_church_office_searches_the_manual_once_the_sync_has_made_it(self):
		frappe.get_doc(
			{
				"doctype": "Flow Model",
				"name": "_Test Manual Chat Model",
				"title": "_Test Manual Chat Model",
				"model_id": "ollama/_test",
				"enabled": 1,
			}
		).db_insert()
		self.assertEqual(self.flow.agents()[0].knowledge, [])

		self.sync()

		office = frappe.get_doc("Flow Agent", self.flow.agents()[0].name)
		self.assertEqual([row.knowledge_base for row in office.knowledge_bases], [KNOWLEDGE_BASE])
		self.assertIn("frappe/search_knowledge", [row.tool for row in office.tools])
