# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Translate with AI: only a public page's published text goes to the model, a members-only page is
refused, and the answer opens as an unpublished, unsaved draft only when it keeps the page's template
tags and adds no script, style, event handler or outside link.

Tests never call a model: runner.start is patched, or Flow's session on a Flow bench.
"""

import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import frappe
from frappe.utils import get_url

from churchit.ai import runner
from churchit.ai.drafts import get_draft
from churchit.ai.test_runner import STAFF, FlowRunnerTestCase, flow_session
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.test_ai import as_user, set_ai
from churchit.church_website import ai
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_two_churches

CONTENT = (
	'<h1>Welcome</h1>\n<p>{{ church_name }} meets <a href="/about">here</a>. See the '
	'<a href="https://example.org/map">map</a>.</p>\n{% if service_time %}<p>Sunday</p>{% endif %}'
)
TRANSLATED = (
	'<h1>Bienvenidos</h1>\n<p>{{ church_name }} se reúne <a href="/about">aquí</a>. Vea el '
	'<a href="https://example.org/map">mapa</a>.</p>\n{% if service_time %}<p>Domingo</p>{% endif %}'
)
CODE = "_Test Translate Secret Script"


def make_page(route: str, **values) -> str:
	return (
		frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": "Welcome",
				"route": route,
				"published": 1,
				"content_type": "HTML",
				"main_section_html": CONTENT,
				"meta_description": "Our church welcomes you.",
				"dynamic_template": 1,
				"javascript": CODE,
				"context_script": f"context.code = {CODE!r}",
				**values,
			}
		)
		.insert(ignore_permissions=True, set_name=f"_test-translate-{frappe.generate_hash(length=8)}")
		.name
	)


def get_values(result: dict) -> dict:
	token = parse_qs(urlparse(result["url"]).query)["ai_draft"][0]
	return get_draft(token)["values"]


class TranslateTestCase(RollbackEachTest):
	"""A Website Manager and a Church Staff user of one branch, and a public HTML page with templates."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, church, _other = make_two_churches()
		cls.editor = ensure_user(
			"_test_translate_editor@example.com", "Translate Editor", ["Church Staff", "Website Manager"]
		)
		cls.staff = ensure_user("_test_translate_staff@example.com", "Translate Staff", ["Church Staff"])
		cls.member = ensure_user("_test_translate_member@example.com", "Translate Member", ["Church User"])
		for user in (cls.editor, cls.staff, cls.member):
			set_user_church(user, church)

	def setUp(self):
		super().setUp()
		set_ai(1)
		frappe.db.set_value("Language", "es", "enabled", 1)
		self.page = make_page("_test-translate-welcome")

	def answer(self, **parts) -> dict:
		return {
			"page": self.page,
			"language": "es",
			"title": "Bienvenidos",
			"content": TRANSLATED,
			"meta_description": "Nuestra iglesia le da la bienvenida.",
			**parts,
		}

	def translate(self, user: str, page: str, language: str = "es"):
		with patch.object(runner, "start", return_value={"token": "t"}) as start:
			as_user(user, ai.translate_web_page, page, language)
		return start


class TestTheRun(TranslateTestCase):
	def test_a_public_page_sends_only_its_published_text_to_writer(self):
		start = self.translate(self.editor, self.page)

		feature, prompt = start.call_args.args
		self.assertEqual(feature, ai.FEATURE)
		self.assertIn(json.dumps(CONTENT, ensure_ascii=False), prompt)
		self.assertIn("Our church welcomes you.", prompt)
		self.assertIn("Español", prompt)
		self.assertNotIn(CODE, prompt)
		self.assertNotIn("sends", start.call_args.kwargs)
		self.assertEqual(start.call_args.kwargs["check"], ai.CHECK)
		self.assertEqual(start.call_args.kwargs["reference_name"], self.page)

	def test_a_members_only_unpublished_or_page_builder_page_is_refused(self):
		pages = {
			"members only": make_page("_test-translate-members", members_only=1),
			"unpublished": make_page("_test-translate-draft", published=0),
			"page builder": make_page("_test-translate-blocks", content_type="Page Builder"),
		}

		for what, page in pages.items():
			with self.subTest(what), self.assertRaises(frappe.ValidationError):
				self.translate(self.editor, page)

	def test_a_user_who_cannot_write_web_pages_a_portal_member_and_ai_off_are_refused(self):
		self.assertRaises(frappe.PermissionError, self.translate, self.staff, self.page)
		self.assertRaises(frappe.PermissionError, self.translate, self.member, self.page)
		set_ai(0)
		self.assertRaises(frappe.PermissionError, self.translate, self.editor, self.page)

	def test_a_language_that_is_not_enabled_is_refused(self):
		frappe.db.set_value("Language", "de", "enabled", 0)
		for language in ("de", "xx-nowhere"):
			with self.subTest(language), self.assertRaises(frappe.ValidationError):
				self.translate(self.editor, self.page, language)


class TestTheCheck(TranslateTestCase):
	def check(self, **parts) -> dict:
		return as_user(self.editor, ai.check_translation, self.answer(**parts))

	def get_values(self, result: dict) -> dict:
		return as_user(self.editor, get_values, result)

	def test_the_answer_opens_an_unpublished_unsaved_new_page(self):
		pages = frappe.db.count("Web Page")

		result = self.check()

		values = self.get_values(result)
		self.assertEqual(frappe.db.count("Web Page"), pages)
		self.assertEqual(values["published"], 0)
		self.assertEqual(values["title"], "Bienvenidos (Español)")
		self.assertEqual(values["route"], "_test-translate-welcome-es")
		self.assertEqual(values["main_section_html"], TRANSLATED)
		self.assertEqual(values["meta_description"], "Nuestra iglesia le da la bienvenida.")
		self.assertEqual((values["content_type"], values["dynamic_template"]), ("HTML", 1))
		self.assertFalse({"javascript", "context_script"} & set(values))
		self.assertEqual(result["page"], self.page)

	def test_a_changed_template_tag_is_refused(self):
		for content in (
			TRANSLATED.replace("{{ church_name }}", "{{ nombre_iglesia }}"),
			TRANSLATED.replace("{% endif %}", ""),
			TRANSLATED + "{{ frappe.session.user }}",
		):
			with self.subTest(content), self.assertRaisesRegex(frappe.ValidationError, "template tag"):
				self.check(content=content)
		with self.assertRaisesRegex(frappe.ValidationError, "template tag"):
			self.check(title="{{ 7 * 7 }}")

	def test_an_added_script_style_handler_or_outside_link_is_refused(self):
		for added in (
			"<script>alert(1)</script>",
			'<img src="x" onerror="alert(1)">',
			'<a href="javascript:alert(1)">x</a>',
			'<a href="&#106;avascript:alert(1)">x</a>',
			'<a href="java&#9;script:alert(1)">x</a>',
			"[x](javascript:alert(1))",
			'<a href="https://evil.example/a">x</a>',
			'<a href="/\\evil.example/a">x</a>',
			'<a href="/&#9;/evil.example/a">x</a>',
			'<a href="http:evil.example">x</a>',
			"Visit www.evil.example today.",
			'<iframe src="/about"></iframe>',
			"<style>body { display: none; }</style>",
		):
			with self.subTest(added), self.assertRaisesRegex(frappe.ValidationError, "added a script"):
				self.check(content=TRANSLATED + added)

	def test_the_links_of_the_page_and_links_to_this_site_pass(self):
		result = self.check(content=f'{TRANSLATED}<a href="{get_url()}/sermons">Sermones</a>')
		self.assertIn("/sermons", self.get_values(result)["main_section_html"])

	def test_an_answer_for_another_or_a_members_only_page_is_refused(self):
		members = make_page("_test-translate-members-only", members_only=1)
		with self.assertRaisesRegex(frappe.ValidationError, "another page"):
			self.check(page="_test-translate-nowhere")
		with self.assertRaises(frappe.ValidationError):
			self.check(page=members)
		with self.assertRaises(frappe.ValidationError):
			self.check(content=12)


class TestOnFlow(FlowRunnerTestCase):
	def test_a_translation_runs_on_writer_whatever_its_label(self):
		self.set_labels("May train", "May train")
		frappe.get_doc("User", STAFF).add_roles("Website Manager")
		frappe.db.set_value("Language", "es", "enabled", 1)
		page = make_page("_test-translate-flow")

		frappe.set_user(STAFF)
		with flow_session() as new_session:
			result = ai.translate_web_page(page, "es")
		frappe.set_user("Administrator")
		self.addCleanup(frappe.cache.delete_value, runner.RUN_KEY + "_test-run")

		self.assertIn("token", result)
		self.assertEqual(new_session.call_args.args[0].name, "churchit/Writer")
		self.assertEqual(new_session.call_args.kwargs, {"title": ai.FEATURE})
