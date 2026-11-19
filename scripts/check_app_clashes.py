# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Find the names that Churchit shares with the apps of the Frappe organization on GitHub.

Frappe keeps one record of each name on a site, so two apps that ship a doctype, report, web form,
route or other record of the same name cannot share a site (see churchit/church_setup/app_names.py).
The install hooks refuse such an app, but only once someone tries to install it. This script finds
the clash before then: it lists every repository of the organization that is not archived and had
a push in the last STALE_DAYS (or has a line in KNOWN_CLASHES), clones only the JSON, www and hooks
files of each Frappe app in it, on its default branch and on the branches named with --branch, and
compares their names with this checkout's.

It needs git and Python 3.10, and nothing else:

    python scripts/check_app_clashes.py                       # every app of github.com/frappe
    python scripts/check_app_clashes.py --repo https://github.com/frappe/hrms --repo <git URL>

KNOWN_CLASHES lists the clashes that are known, each with the reason it stays. The script exits
with 1 when it finds a clash that is not listed, when it cannot read a repository, or, in a full
run, when a listed clash is gone, so that the list stays true. The GitHub workflow app-clashes.yml runs it each week. Set GITHUB_TOKEN
to raise GitHub's limit on listing repositories.
"""

import argparse
import concurrent.futures
import datetime
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_ROOT)  # app_names needs only the standard library
from churchit.church_setup.app_names import get_shared_names, get_shipped_names

ORGANIZATION = "frappe"
BRANCHES = ("version-16",)
# Repositories with no push in this many days are left out: no site installs them any more.
STALE_DAYS = 3 * 365

# (repository, doctype, name): the reason the clash stays. Delete a line when its clash is gone.
# "Not renamed yet" means the install hooks refuse that app on a Churchit site.
KNOWN_CLASHES = {
	("frappe", "Route", "about"): "Churchit replaces Frappe's own page on purpose.",
	("frappe", "Route", "contact"): "Churchit replaces Frappe's own page on purpose.",
	("frappe", "Route", "portal"): "Churchit replaces Frappe's own page on purpose.",
	("lms", "DocType", "Function"): "Not renamed yet.",
	("education", "DocType", "Room"): "Not renamed yet.",
	("education", "DocType", "Room Booking"): "Not renamed yet.",
	("lending", "DocType", "Pledge"): "Not renamed yet.",
	("healthcare", "Web Form", "personal-details"): "Not renamed yet.",
	("healthcare", "Route", "personal-details"): "Not renamed yet.",
	("mail", "DocType", "Email Address"): "Not renamed yet.",
	("mail", "DocType", "Push Subscription"): "Not renamed yet.",
	("suite", "DocType", "Email Address"): "Not renamed yet.",
	("suite", "DocType", "Push Subscription"): "Not renamed yet.",
	("suite", "DocType", "Slide"): "Not renamed yet.",
	("suite", "Route", "calendar"): "Not renamed yet. Suite's website_route_rules take /calendar.",
	("Letters", "DocType", "Letter"): "Not renamed yet.",
	("non_profit", "DocType", "Donation"): "Not renamed yet. Non Profit has had no change since 2024.",
	("non_profit", "DocType", "Membership Type"): "Not renamed yet. Non Profit has had no change since 2024.",
	("meeting", "DocType", "Meeting Attendee"): "Not renamed yet. Meeting's code has not changed since 2016.",
}


def main(argv: list[str]) -> int:
	"""Check the repositories that *argv* names, or all of them; the exit status."""
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--repo", action="append", help="check only this git URL (repeat for more)")
	parser.add_argument(
		"--branch", action="append", help=f"also check this branch (default {', '.join(BRANCHES)})"
	)
	parser.add_argument("--cache", help="keep the clones in this folder and reuse them")
	options = parser.parse_args(argv)

	branches = tuple(options.branch or BRANCHES)
	repos = options.repo or list_repositories(ORGANIZATION)
	ours = get_shipped_names(os.path.join(APP_ROOT, "churchit"))
	with tempfile.TemporaryDirectory() as temporary:
		folder = options.cache or temporary
		with concurrent.futures.ThreadPoolExecutor(8) as pool:
			results = list(pool.map(lambda url: check_repository(url, branches, ours, folder), repos))
	found = {clash: where for result, _failed in results for clash, where in result.items()}
	failed = sorted(failure for _result, failures in results for failure in failures)
	return report(found, failed, full_run=not options.repo)


def list_repositories(organization: str) -> list[str]:
	"""The clone URL of each repository of *organization* that is not archived and still changes.

	A repository with a line in KNOWN_CLASHES is kept however old it is, so its clash is not read as gone.
	"""
	listed = {repository for repository, _doctype, _name in KNOWN_CLASHES}
	since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=STALE_DAYS)
	urls, page = [], 1
	while True:
		repos = get_json(f"https://api.github.com/orgs/{organization}/repos?per_page=100&page={page}")
		for repo in repos:
			pushed = datetime.datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
			if not repo["archived"] and (pushed >= since or repo["name"] in listed):
				urls.append(repo["clone_url"])
		if len(repos) < 100:
			return sorted(urls)
		page += 1


def get_json(url: str) -> list | dict:
	"""The JSON that the GitHub API answers at *url*."""
	request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
	if os.environ.get("GITHUB_TOKEN"):
		request.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
	with urllib.request.urlopen(request, timeout=60) as response:
		return json.load(response)


def check_repository(url: str, branches: tuple[str, ...], ours: dict, folder: str) -> tuple[dict, list]:
	"""The names the app at *url* shares with *ours*, and the branches that could not be read.

	The names are {(repository, doctype, name): "branch: path"}; the branches are "repository@branch".
	"""
	repository = get_repository(url)
	found, failed = {}, []
	for branch in (None, *branches):
		try:
			package = clone(url, branch, os.path.join(folder, f"{repository}@{branch or 'default'}"))
		except subprocess.CalledProcessError:
			failed.append(f"{repository}@{branch or 'default branch'}")
			if branch:
				continue
			break
		if not package:
			continue
		for name, theirs in get_shared_names(ours, get_shipped_names(package)):
			where = f"{branch or 'default branch'}: {theirs.path}"
			found.setdefault((repository, name.doctype, name.name), where)
	return found, failed


def get_repository(url: str) -> str:
	"""The repository name at the end of *url*."""
	return url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]


def clone(url: str, branch: str | None, folder: str) -> str | None:
	"""Clone the JSON and www files of the Frappe app at *url* into *folder*; its package path, or None.

	None when the branch is missing or the repository holds no Frappe app. Raises CalledProcessError
	when git cannot read the repository, after a second try.
	"""
	if branch and not has_branch(url, branch):
		return None
	if not os.path.isdir(folder):
		command = ["git", "clone", "--quiet", "--depth=1", "--filter=blob:none", "--no-checkout"]
		branch_options = ["--branch", branch] if branch else []
		if subprocess.run([*command, *branch_options, url, folder], capture_output=True).returncode:
			subprocess.run([*command, *branch_options, url, folder], capture_output=True, check=True)
	package = get_package(folder)
	if not package:
		return None
	patterns = [f"/{package}/{name}" for name in ("modules.txt", "hooks.py", "**/*.json", "www/")]
	git(folder, "sparse-checkout", "set", "--no-cone", *patterns)
	git(folder, "checkout", "--quiet")
	return os.path.join(folder, package)


def has_branch(url: str, branch: str) -> bool:
	"""Whether the repository at *url* has *branch*. Raises CalledProcessError when git cannot read it."""
	command = ["git", "ls-remote", "--exit-code", "--heads", url, branch]
	result = subprocess.run(command, capture_output=True)
	if result.returncode == 2:  # git's answer when no branch matches
		return False
	if result.returncode:
		subprocess.run(command, capture_output=True, check=True)
	return True


def get_package(folder: str) -> str | None:
	"""The folder of the repository at *folder* that holds a Frappe app's hooks.py and modules.txt."""
	files = set(git(folder, "ls-tree", "--name-only", "-r", "HEAD").split("\n"))
	packages = sorted(
		path.split("/")[0] for path in files if path.count("/") == 1 and path.endswith("/hooks.py")
	)
	return next((package for package in packages if f"{package}/modules.txt" in files), None)


def git(folder: str, *arguments: str) -> str:
	"""The output of git *arguments* in *folder*."""
	return subprocess.run(
		["git", "-C", folder, *arguments], capture_output=True, text=True, check=True
	).stdout


def report(found: dict, failed: list[str], full_run: bool) -> int:
	"""Print what was found; 1 when KNOWN_CLASHES is out of date or a repository could not be read."""
	unread = {failure.split("@")[0] for failure in failed}
	new = sorted(clash for clash in found if clash not in KNOWN_CLASHES)
	gone = sorted(clash for clash in KNOWN_CLASHES if clash not in found and clash[0] not in unread)
	gone = gone if full_run else []
	lines = ["# Names Churchit shares with Frappe apps", ""]
	lines += [f"- {' '.join(clash)} ({found[clash]})" for clash in sorted(found)] or ["None."]
	if new:
		lines += [
			"",
			"## New clashes",
			"",
			"Rename the Churchit record, or add a line to KNOWN_CLASHES with the reason.",
		]
		lines += [f"- {' '.join(clash)} ({found[clash]})" for clash in new]
	if failed:
		lines += ["", "## Not read", "", "git could not read these, so their clashes are unknown. Run again."]
		lines += [f"- {failure}" for failure in failed]
	if gone:
		lines += ["", "## Gone", "", "Delete these lines from KNOWN_CLASHES:"]
		lines += [f"- {' '.join(clash)}" for clash in gone]
	text = "\n".join(lines) + "\n"
	print(text)
	if os.environ.get("GITHUB_STEP_SUMMARY"):
		with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
			summary.write(text)
	return 1 if new or gone or failed else 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
