# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fix the shipped missions and home Web Pages on existing sites.

A missionary card has a body only when the missionary has a photo, names the country in text beside
its flag, and loses an email link that never showed, because Missionary has no email field. The
missionary's title and website are escaped, and the empty state is translated. The next gathering
on the home page is a named section, not an aside inside the main content, and a screen reader skips
the home page emoji.

The pages are user-owned starter data. Each group below replaces text this app shipped, and it
applies only when the page still has all of its shipped text, so a page the church rewrote stays
as it is.
"""

from churchit.patches.v1_0.fix_shipped_sermon_excerpt_and_missions_map import fix_page

PHOTO = '<img src="{{ missionary.photo }}" alt="{{ missionary.title | e }}">'
COUNTRY_CODE = "{% set country_code = country_codes.get(missionary.country) %}\n"
FLAG = '<img src="https://flagcdn.com/w40/{{ country_code | lower }}.png"'

MISSIONARY_PHOTO = (
	(
		'            <div class="card-body">\n'
		"                {% if missionary.photo %}\n"
		'                    <p class="card-text">\n'
		f"                        {PHOTO}\n"
		"                    </p>\n"
		"                {% endif %}\n"
		"            </div>\n"
		'            <div class="card-footer">\n',
		"            {% if missionary.photo %}\n"
		'            <div class="card-body">\n'
		'                <p class="card-text">\n'
		f"                    {PHOTO}\n"
		"                </p>\n"
		"            </div>\n"
		"            {% endif %}\n"
		'            <div class="card-footer mt-auto">\n',
	),
)

MISSIONARY_COUNTRY = (
	(
		"                    {% if missionary.email %}\n"
		'                        <a href="mailto:{{ missionary.email }}">{{ missionary.email }} </a>\n'
		"                    {% endif %}\n"
		f"                    {COUNTRY_CODE}"
		"                    {% if country_code %}\n"
		f"                        {FLAG}\n"
		'                             alt="{{ missionary.country }} flag"\n'
		'                             title="{{ missionary.country }} flag"\n'
		'                             style="width: 2em">\n'
		"                    {% endif %}\n",
		"                    {% if missionary.country %}\n"
		'                    <span class="text-nowrap">\n'
		f"                        {COUNTRY_CODE}"
		"                        {% if country_code %}\n"
		f'                        {FLAG} alt="" style="width: 2em">\n'
		"                        {% endif %}\n"
		"                        {{ missionary.country | e }}\n"
		"                    </span>\n"
		"                    {% endif %}\n",
	),
)

# Staff type the title and website, and the public page shows them, so each is escaped. One group
# each, so a church that edited one of them still gets the others.
MISSIONARY_TITLE = (("{{ missionary.title }}\n", "{{ missionary.title | e }}\n"),)

MISSIONARY_WEBSITE = (
	(
		'<a href="{{ missionary.website }}" target="_blank"> {{ missionary.website }}</a>',
		'<a href="{{ missionary.website | e }}" target="_blank" rel="noopener"> {{ missionary.website | e }}</a>',
	),
)

MISSIONS_EMPTY = (
	(
		">Our missions information is being updated. Please check back soon.</p>",
		'>{{ _("Our missions information is being updated. Please check back soon.") }}</p>',
	),
)

NEXT_GATHERING = (
	(
		'<aside class="card home-aside">',
		'<section class="card home-aside" aria-labelledby="home-next-gathering">',
	),
	(
		'<h2 class="home-aside-title">{{ next_up.function_name or next_up.title }}</h2>',
		'<h2 class="home-aside-title" id="home-next-gathering">{{ next_up.function_name or next_up.title }}</h2>',
	),
	("\t</aside>\n\t{% endif %}\n</section>", "\t</section>\n\t{% endif %}\n</section>"),
)

HOME_EMOJI = (
	("📍 {{ address_line }}", '<span aria-hidden="true">📍</span> {{ address_line }}'),
	('🎧 {{ _("Latest message") }}', '<span aria-hidden="true">🎧</span> {{ _("Latest message") }}'),
	('📅 {{ _("Upcoming") }}', '<span aria-hidden="true">📅</span> {{ _("Upcoming") }}'),
)

GROUPS = {
	"missions": (MISSIONARY_PHOTO, MISSIONARY_COUNTRY, MISSIONARY_TITLE, MISSIONARY_WEBSITE, MISSIONS_EMPTY),
	"home": (NEXT_GATHERING, HOME_EMOJI),
}


def execute():
	for name, groups in GROUPS.items():
		fix_page(name, groups)
