# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The master AI switch: the desk boot, Frappe's MCP server, who may sign in an AI app and use MCP,
the upgrade notice, the notice when a person connects an app, and the exposure panel."""

import sys
from unittest.mock import patch
from urllib.parse import urlencode

import frappe
import frappe.mcp
from frappe.auth import validate_auth
from frappe.core.doctype.system_settings.system_settings import clear_system_settings_cache
from frappe.core.doctype.user.user import generate_keys
from frappe.integrations.utils import OAuth2DynamicClientMetadata, create_new_oauth_client
from frappe.oauth import OAuthWebRequestValidator
from werkzeug.exceptions import NotFound
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from churchit.ai.exposure import get_exposure
from churchit.ai.reports import NO_EXPLAIN
from churchit.ai.switch import (
	AI_APPS_REPORT,
	AI_ROLES,
	MCP_PATH,
	SETTINGS,
	close_mcp_while_ai_off,
	extend_bootinfo,
	get_mcp_closed_message,
	has_flow,
	is_ai_on,
	refuse_mcp_to_other_users,
	require_ai,
)
from churchit.church_people.doctype.person.test_person import ensure_outgoing_email_account
from churchit.patches.v1_0 import church_ai_off_by_default
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_two_churches

MANAGER = "_test_ai_system_manager@example.com"


def set_ai(enabled: int) -> None:
	frappe.db.set_single_value(SETTINGS, "enabled", enabled)


def set_mcp(enabled: int) -> None:
	frappe.db.set_single_value("System Settings", "enable_mcp", enabled)
	clear_system_settings_cache()


def get_system_settings():
	"""System Settings ready to save: a test site that skipped the setup wizard has no language or time zone."""
	settings = frappe.get_doc("System Settings")
	settings.language = settings.language or "en"
	settings.time_zone = settings.time_zone or "UTC"
	return settings


def get_mcp() -> int:
	return frappe.db.get_single_value("System Settings", "enable_mcp")


def make_client(app_name: str, roles: tuple[str, ...] = ()) -> str:
	"""An OAuth Client that an admin makes in the desk, with *roles* as its Allowed Roles."""
	return (
		frappe.get_doc(
			{
				"doctype": "OAuth Client",
				"app_name": app_name,
				"scopes": "all",
				"redirect_uris": "http://localhost",
				"default_redirect_uri": "http://localhost",
				"allowed_roles": [{"role": role} for role in roles],
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def register_client(app_name: str) -> str:
	"""An OAuth Client that an MCP client registers itself, through dynamic client registration."""
	metadata = OAuth2DynamicClientMetadata(
		client_name=app_name,
		redirect_uris=["http://localhost:6274/oauth/callback"],
		token_endpoint_auth_method="none",
	)
	return create_new_oauth_client(metadata).name


def get_allowed_roles(client: str) -> list[str]:
	return sorted(row.role for row in frappe.get_doc("OAuth Client", client).allowed_roles)


def connect(client: str, user: str) -> str:
	"""Store a token as Frappe's token endpoint does, in a request that runs as Guest."""
	frappe.set_user("Guest")
	try:
		token = frappe.get_doc(
			{
				"doctype": "OAuth Bearer Token",
				"client": client,
				"user": user,
				"scopes": "all",
				"access_token": frappe.generate_hash(),
				"refresh_token": frappe.generate_hash(),
				"expires_in": 3600,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")
	return token.name


class SwitchTestCase(RollbackEachTest):
	def tearDown(self):
		super().tearDown()
		clear_system_settings_cache()


class TestSwitch(SwitchTestCase):
	def test_ai_starts_off(self):
		self.assertEqual(frappe.get_meta(SETTINGS).get_field("enabled").default, "0")
		set_ai(0)
		self.assertFalse(is_ai_on())

	def test_require_ai_refuses_while_ai_is_off_and_says_why(self):
		set_ai(0)
		frappe.clear_messages()
		self.assertRaises(frappe.PermissionError, require_ai, "test")
		messages = [message.get("message") for message in frappe.local.message_log]
		self.assertIn("AI is turned off on this site.", messages)

		set_ai(1)
		require_ai("test")

	def test_boot_tells_the_desk_ai_is_off_and_keeps_the_church_keys(self):
		set_ai(0)
		bootinfo = frappe._dict(churchit={"multi_church": False})
		with patch("churchit.ai.switch.has_flow", return_value=False):
			extend_bootinfo(bootinfo)
		self.assertEqual(
			bootinfo.churchit,
			{
				"multi_church": False,
				"ai": {
					"on": False,
					"flow": False,
					"flow_ready": False,
					"actions": False,
					"private_actions": False,
					"no_explain": list(NO_EXPLAIN),
				},
			},
		)

	def test_boot_says_whether_flow_can_run_churchits_agents(self):
		if not has_flow():
			self.skipTest("This Frappe does not ship Flow.")
		for ready in (True, False):
			bootinfo = frappe._dict()
			with patch("churchit.ai.flow_models.is_flow_ready", return_value=ready):
				extend_bootinfo(bootinfo)
			self.assertTrue(bootinfo.churchit["ai"]["flow"])
			self.assertEqual(bootinfo.churchit["ai"]["flow_ready"], ready)

	def test_boot_loads_no_flow_code(self):
		"""A Flow update that moves a name must not stop the desk from booting."""
		if flow := sys.modules.pop("churchit.ai.flow", None):
			self.addCleanup(sys.modules.__setitem__, "churchit.ai.flow", flow)
		extend_bootinfo(frappe._dict())
		self.assertNotIn("churchit.ai.flow", sys.modules)

	def test_boot_adds_ai_after_church_scope_sets_the_churchit_keys(self):
		"""church_scope replaces frappe.boot.churchit, so it must run first."""
		hooks = frappe.get_hooks("extend_bootinfo")
		self.assertLess(
			hooks.index("churchit.church_scope.extend_bootinfo"),
			hooks.index("churchit.ai.switch.extend_bootinfo"),
		)


class TestMCPFollowsTheSwitch(SwitchTestCase):
	def test_system_settings_still_has_enable_mcp(self):
		"""close_mcp does nothing without it, so a Frappe that renames the field fails here."""
		self.assertTrue(frappe.get_meta("System Settings").has_field("enable_mcp"))

	def test_mcp_answers_not_found_while_ai_is_off(self):
		set_ai(0)
		set_mcp(1)
		self.assertTrue(close_mcp_while_ai_off())
		self.assertRaises(NotFound, frappe.mcp.handle)

	def test_migrate_closes_mcp_that_a_frappe_patch_opened(self):
		hook = "churchit.ai.switch.close_mcp_while_ai_off"
		self.assertIn(hook, frappe.get_hooks("after_migrate"))
		set_ai(0)
		set_mcp(1)
		frappe.get_attr(hook)()
		self.assertEqual(get_mcp(), 0)

	def test_migrate_leaves_mcp_alone_while_ai_is_on(self):
		set_ai(1)
		set_mcp(1)
		self.assertFalse(close_mcp_while_ai_off())
		self.assertEqual(get_mcp(), 1)

	def test_system_settings_refuse_opening_mcp_while_ai_is_off(self):
		set_ai(0)
		set_mcp(0)
		settings = get_system_settings()
		settings.enable_mcp = 1
		self.assertRaisesRegex(frappe.ValidationError, "Church AI Settings", settings.save)

	def test_other_system_settings_still_save_while_ai_is_off(self):
		set_ai(0)
		set_mcp(0)
		settings = get_system_settings()
		settings.agent_instructions = "_Test instructions"
		settings.save()
		self.assertEqual(
			frappe.db.get_single_value("System Settings", "agent_instructions"), "_Test instructions"
		)

	def test_a_frappe_patch_that_opens_mcp_does_not_stop_the_migrate(self):
		"""The refusal is for people; after_migrate closes MCP again."""
		set_ai(0)
		set_mcp(0)
		settings = get_system_settings()
		settings.enable_mcp = 1
		frappe.flags.in_patch = True
		try:
			settings.save()
		finally:
			frappe.flags.in_patch = False
		self.assertEqual(get_mcp(), 1)

		close_mcp_while_ai_off()
		self.assertEqual(get_mcp(), 0)

	def test_system_settings_open_mcp_while_ai_is_on(self):
		set_ai(1)
		set_mcp(0)
		settings = get_system_settings()
		settings.enable_mcp = 1
		settings.save()
		self.assertEqual(get_mcp(), 1)


class TestOnlyTrustedUsersSignInAnApp(SwitchTestCase):
	"""Frappe's sign-in asks OAuthWebRequestValidator.validate_client_id, which asks
	OAuthClient.user_has_allowed_role as the signed-in user."""

	def may_sign_in(self, client: str, user: str) -> bool:
		frappe.set_user(user)
		try:
			return OAuthWebRequestValidator().validate_client_id(client, frappe._dict())
		finally:
			frappe.set_user("Administrator")

	def test_an_app_that_registers_itself_is_only_for_the_ai_roles(self):
		self.assertIn(
			"churchit.ai.switch.limit_new_app_to_ai_roles",
			frappe.get_hooks("doc_events")["OAuth Client"]["before_insert"],
		)
		self.assertEqual(get_allowed_roles(register_client("_Test MCP App")), sorted(AI_ROLES))

	def test_only_managers_and_church_ai_users_sign_in_an_app_that_registers_itself(self):
		client = register_client("_Test MCP App")
		users = {
			roles: ensure_user(f"_test_ai_sign_in_{index}@example.com", "AI Sign In", roles=roles)
			for index, roles in enumerate(
				[
					("Church Staff",),
					("Church Staff", "Church Pastoral Care"),
					("Church User",),
					("Church Manager",),
					("System Manager",),
					("Church Staff", "Church AI User"),
				]
			)
		}
		allowed = {roles for roles, user in users.items() if self.may_sign_in(client, user)}
		self.assertEqual(
			allowed, {("Church Manager",), ("System Manager",), ("Church Staff", "Church AI User")}
		)

	def test_an_app_made_with_roles_keeps_them(self):
		client = make_client("_Test Staff App", roles=("Church Staff",))
		self.assertEqual(get_allowed_roles(client), ["Church Staff"])

		staff = ensure_user("_test_ai_sign_in_staff_app@example.com", "AI Staff", roles=("Church Staff",))
		self.assertTrue(self.may_sign_in(client, staff))

	def test_the_church_ai_user_role_opens_no_desk_and_no_record(self):
		role = frappe.get_doc("Role", "Church AI User")
		self.assertEqual(role.desk_access, 0)
		self.assertFalse(frappe.db.exists("DocPerm", {"role": role.name}))
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"role": role.name}))
		self.assertFalse(frappe.db.exists("Has Role", {"role": role.name, "parenttype": "Role Profile"}))

	def test_the_church_ai_user_role_leaves_a_member_a_website_user(self):
		"""A System User escapes the member scoping of Person and Family."""
		member = ensure_user(
			"_test_ai_member@example.com", "AI Member", roles=("Church User", "Church AI User")
		)
		self.assertEqual(frappe.db.get_value("User", member, "user_type"), "Website User")


class TestMCPOnlyForTheAIRoles(SwitchTestCase):
	"""Frappe runs auth_hooks in validate_auth, once a session, an API key or a token has set the user."""

	LOCALS = ("request", "request_ip", "login_manager")

	def setUp(self):
		super().setUp()
		self.saved = {name: getattr(frappe.local, name, None) for name in self.LOCALS}
		self.staff = ensure_user("_test_ai_mcp_staff@example.com", "AI MCP Staff", roles=("Church Staff",))
		self.ai_user = ensure_user(
			"_test_ai_mcp_ai_user@example.com", "AI MCP User", roles=("Church Staff", "Church AI User")
		)

	def tearDown(self):
		for name, value in self.saved.items():
			setattr(frappe.local, name, value)
		super().tearDown()

	def send(self, path: str = MCP_PATH, headers: dict | None = None) -> None:
		"""Start a request to *path*, as Frappe's app does before it authenticates."""
		frappe.local.request = Request(
			EnvironBuilder(path=path, method="POST", headers=headers).get_environ()
		)
		frappe.local.request_ip = "127.0.0.1"
		frappe.local.login_manager = frappe._dict(user="Guest")

	def may_use_mcp(self, user: str, path: str = MCP_PATH) -> bool:
		self.send(path)
		frappe.set_user(user)
		try:
			refuse_mcp_to_other_users()
			return True
		except frappe.PermissionError:
			return False
		finally:
			frappe.set_user("Administrator")

	def test_frappe_asks_churchit_at_every_request(self):
		self.assertIn("churchit.ai.switch.refuse_mcp_to_other_users", frappe.get_hooks("auth_hooks"))

	def test_a_signed_in_desk_user_without_an_ai_role_is_refused_mcp(self):
		self.assertFalse(self.may_use_mcp(self.staff))
		self.assertFalse(self.may_use_mcp(self.staff, MCP_PATH + "/"))
		self.assertTrue(self.may_use_mcp(self.staff, "/api/v2/method/frappe.auth.get_logged_user"))

	def test_the_ai_roles_use_mcp(self):
		manager = ensure_user("_test_ai_mcp_manager@example.com", "AI MCP Manager", roles=("Church Manager",))
		for user in (self.ai_user, manager, "Administrator"):
			self.assertTrue(self.may_use_mcp(user), user)

	def test_a_guest_goes_on_to_frappes_sign_in(self):
		"""Frappe's 401 tells an AI app where to sign in."""
		self.assertTrue(self.may_use_mcp("Guest"))

	def use_mcp_with_an_api_key(self, user: str) -> None:
		"""Authenticate an MCP request with *user*'s API key, as Frappe's app does."""
		frappe.set_user("Administrator")
		keys = generate_keys(user)
		self.send(headers={"Authorization": f"token {keys['api_key']}:{keys['api_secret']}"})
		frappe.set_user("Guest")
		validate_auth()

	def test_an_api_key_without_an_ai_role_is_refused_mcp(self):
		self.assertRaises(frappe.PermissionError, self.use_mcp_with_an_api_key, self.staff)
		self.use_mcp_with_an_api_key(self.ai_user)
		self.assertEqual(frappe.session.user, self.ai_user)

	def test_removing_the_role_closes_mcp_at_the_next_request(self):
		self.assertTrue(self.may_use_mcp(self.ai_user))
		user = frappe.get_doc("User", self.ai_user)
		user.remove_roles("Church AI User")
		self.assertFalse(self.may_use_mcp(self.ai_user))


class TestAIOffByDefaultPatch(SwitchTestCase):
	def notices(self) -> list[str]:
		return frappe.get_all(
			"Notification Log",
			filters={"for_user": MANAGER, "document_type": SETTINGS},
			pluck="email_content",
		)

	def test_upgrade_closes_mcp_and_tells_each_system_manager_once(self):
		ensure_user(MANAGER, "AI Manager", roles=("System Manager",))
		set_ai(0)
		set_mcp(1)

		church_ai_off_by_default.execute()
		self.assertEqual(get_mcp(), 0)
		self.assertEqual(len(self.notices()), 1)
		self.assertIn("/desk/oauth-settings", self.notices()[0])
		self.assertIn("Church AI User", self.notices()[0])

		church_ai_off_by_default.execute()
		self.assertEqual(len(self.notices()), 1)

	def test_upgrade_leaves_a_closed_mcp_and_says_nothing(self):
		ensure_user(MANAGER, "AI Manager", roles=("System Manager",))
		set_ai(0)
		set_mcp(0)
		church_ai_off_by_default.execute()
		self.assertEqual(self.notices(), [])

	def test_the_notice_names_the_other_business_apps(self):
		if not {"erpnext", "payments"} <= set(frappe.get_all_apps()):
			self.skipTest("The bench has no ERPNext or no Payments to read the hooks of.")
		with patch("frappe.get_installed_apps", return_value=["frappe", "payments", "churchit", "erpnext"]):
			message = get_mcp_closed_message()
		self.assertIn("ERPNext", message)
		self.assertNotIn("Payments", message)
		with patch("frappe.get_installed_apps", return_value=["frappe", "payments", "churchit"]):
			self.assertNotIn("users of", get_mcp_closed_message())


class TestAIAppNotice(SwitchTestCase):
	def setUp(self):
		super().setUp()
		ensure_outgoing_email_account()
		self.manager = ensure_user(MANAGER, "AI Manager", roles=("System Manager",))
		self.user = ensure_user("_test_ai_connector@example.com", "AI Connector")
		self.client = make_client("_Test <b>AI</b> App")

	def notices(self) -> list[dict]:
		return frappe.get_all(
			"Notification Log",
			filters={"for_user": self.manager, "document_type": "OAuth Client", "document_name": self.client},
			fields=["subject", "email_content"],
		)

	def test_the_first_token_of_a_user_and_app_tells_system_managers(self):
		connect(self.client, self.user)

		notices = self.notices()
		self.assertEqual(len(notices), 1)
		self.assertIn(self.user, notices[0].subject)
		self.assertIn("&lt;b&gt;AI&lt;/b&gt;", notices[0].email_content)
		self.assertNotIn("<b>AI", notices[0].email_content)
		self.assertIn(f"can now see and change what {self.user} can see and change", notices[0].email_content)
		revoke = urlencode({"user": self.user, "client": self.client}).replace("&", "&amp;")
		self.assertIn(f"/desk/oauth-bearer-token?{revoke}", notices[0].email_content)
		self.assertTrue(
			frappe.db.exists(
				"Email Queue", {"reference_doctype": "OAuth Client", "reference_name": self.client}
			)
		)

	def test_a_refreshed_token_says_nothing(self):
		connect(self.client, self.user)
		connect(self.client, self.user)
		self.assertEqual(len(self.notices()), 1)

	def test_a_sign_in_after_a_revoke_tells_system_managers_again(self):
		"""Frappe's revoke endpoint and the OAuth Bearer Token form leave a Revoked row."""
		token = connect(self.client, self.user)
		frappe.db.set_value("OAuth Bearer Token", token, "status", "Revoked")
		connect(self.client, self.user)
		self.assertEqual(len(self.notices()), 2)

	def test_registering_an_app_without_a_sign_in_says_nothing(self):
		make_client("_Test Registered Only")
		self.assertEqual(self.notices(), [])

	def test_a_token_has_no_church_and_still_reaches_a_branch_system_manager(self):
		_root, branch, _other = make_two_churches()
		frappe.get_doc(
			{"doctype": "User Permission", "user": self.manager, "allow": "Church", "for_value": branch}
		).insert(ignore_permissions=True)
		connect(self.client, self.user)
		self.assertEqual(len(self.notices()), 1)

	def test_the_bell_notice_comes_without_an_outgoing_email_account(self):
		"""The person's sign-in must not fail, so a missing account is logged."""
		with patch("frappe.sendmail", side_effect=frappe.OutgoingEmailError):
			connect(self.client, self.user)
		self.assertEqual(len(self.notices()), 1)

	def test_no_notice_email_or_report_holds_the_token(self):
		"""OAuth Bearer Token names each row by its access token."""
		token = connect(self.client, self.user)

		for doctype, field in (
			("Notification Log", "document_name"),
			("Notification Log", "email_content"),
			("Email Queue", "reference_name"),
			("Email Queue", "message"),
			("Communication", "reference_name"),
		):
			self.assertFalse(frappe.db.exists(doctype, {field: ("like", f"%{token}%")}), (doctype, field))
		_columns, rows = frappe.get_doc("Report", AI_APPS_REPORT).get_data(as_dict=True)
		self.assertNotIn(token, frappe.as_json(rows))

	def test_the_connected_ai_apps_report_lists_the_person_and_app(self):
		connect(self.client, self.user)
		connect(self.client, self.user)

		_columns, rows = frappe.get_doc("Report", AI_APPS_REPORT).get_data(as_dict=True)
		row = next(row for row in rows if row.client == self.client)
		self.assertEqual((row.user, row.app_name, row.tokens), (self.user, "_Test <b>AI</b> App", 2))


class TestExposure(SwitchTestCase):
	def lines(self, user: str) -> dict[str, dict]:
		frappe.set_user(user)
		try:
			return {line["surface"]: line for line in get_exposure()}
		finally:
			frappe.set_user("Administrator")

	def test_church_users_and_website_users_are_refused(self):
		church_user = ensure_user("_test_ai_church_user@example.com", "AI Church User")
		website_user = ensure_user("_test_ai_website_user@example.com", "AI Website User", roles=())
		for user in (church_user, website_user):
			frappe.set_user(user)
			self.assertRaises(frappe.PermissionError, get_exposure)
			frappe.set_user("Administrator")

	def test_a_church_manager_sees_the_doors_but_no_apps_keys_or_people(self):
		connect(make_client("_Test Hidden App"), "Administrator")
		make_client("_Test Hidden Open App", roles=("Desk User",))
		manager = ensure_user("_test_ai_church_manager@example.com", "AI Church Manager", ("Church Manager",))
		lines = self.lines(manager)

		self.assertIn("Frappe MCP server", lines)
		for surface in (
			"Connected apps",
			"API keys",
			"People who may connect an AI app",
			"Apps open to every desk user",
		):
			self.assertEqual(lines[surface]["state"], "Ask a System Manager")
		self.assertNotIn("_Test Hidden", frappe.as_json(lines))

	def test_a_system_manager_sees_who_may_connect_an_ai_app(self):
		manager = ensure_user(MANAGER, "AI Manager", roles=("System Manager",))
		before = self.lines(manager)["People who may connect an AI app"]["state"]
		ensure_user(
			"_test_ai_exposure_ai_user@example.com", "AI User", roles=("Church Staff", "Church AI User")
		)
		ensure_user("_test_ai_exposure_staff@example.com", "AI Staff", roles=("Church Staff",))
		ensure_user(
			"_test_ai_exposure_member@example.com", "AI Member", roles=("Church User", "Church AI User")
		)

		line = self.lines(manager)["People who may connect an AI app"]
		self.assertEqual(int(line["state"].split()[0]), int(before.split()[0]) + 1)
		self.assertIn("/app/user?", line["link"])
		self.assertIn("Church+AI+User", line["link"])

	def test_a_system_manager_sees_each_app_that_every_desk_user_may_sign_in(self):
		manager = ensure_user(MANAGER, "AI Manager", roles=("System Manager",))
		open_client = make_client("_Test Open App", roles=("Desk User",))
		everyone_client = make_client("_Test Everyone App", roles=("All",))
		make_client("_Test Staff App", roles=("Church Staff",))
		register_client("_Test Registered App")

		lines = self.lines(manager)
		self.assertEqual(lines["App open to every desk user: _Test Open App"]["state"], "Every desk user")
		self.assertEqual(
			lines["App open to every desk user: _Test Open App"]["link"], f"/app/oauth-client/{open_client}"
		)
		self.assertEqual(lines["App open to every desk user: _Test Everyone App"]["state"], "Every user")
		self.assertIn(everyone_client, lines["App open to every desk user: _Test Everyone App"]["link"])
		self.assertNotIn("_Test Staff App", frappe.as_json(lines))
		self.assertNotIn("_Test Registered App", frappe.as_json(lines))

	def test_a_system_manager_sees_mcp_registration_and_connected_apps(self):
		manager = ensure_user(MANAGER, "AI Manager", roles=("System Manager",))
		set_ai(1)
		set_mcp(1)
		frappe.db.set_single_value("OAuth Settings", "enable_dynamic_client_registration", 1)
		client = make_client("_Test Seen App")
		connect(client, "Administrator")
		connect(client, "Administrator")

		lines = self.lines(manager)
		self.assertTrue(lines["Churchit AI"]["open"])
		self.assertTrue(lines["Frappe MCP server"]["open"])
		self.assertEqual(lines["Frappe MCP server"]["link"], "/app/system-settings")
		self.assertTrue(lines["Dynamic client registration"]["open"])
		self.assertEqual(lines["Connected app: _Test Seen App"]["state"], "1 person")

		set_ai(0)
		close_mcp_while_ai_off()
		frappe.db.set_single_value("OAuth Settings", "enable_dynamic_client_registration", 0)
		lines = self.lines(manager)
		self.assertFalse(lines["Frappe MCP server"]["open"])
		self.assertFalse(lines["Dynamic client registration"]["open"])

	def test_api_keys_are_counted(self):
		manager = ensure_user(MANAGER, "AI Manager", roles=("System Manager",))
		before = len(frappe.get_all("User", filters={"enabled": 1, "api_key": ("is", "set")}))
		frappe.db.set_value("User", manager, "api_key", frappe.generate_hash(length=15))
		state = self.lines(manager)["API keys"]["state"]
		self.assertEqual(state, "1 person" if before == 0 else f"{before + 1} people")

	def test_apps_that_are_not_installed_say_so(self):
		with patch("frappe.get_installed_apps", return_value=["frappe", "churchit"]):
			lines = self.lines("Administrator")
		for surface in ("Frappe Builder AI", "Frappe Assistant Core", "Raven AI"):
			self.assertEqual(lines[surface]["state"], "Not installed")
			self.assertIsNone(lines[surface]["link"])
