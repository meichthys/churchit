/** What member_portal.py puts in the page as it loads (churchit/portal/boot.py). */
export interface NavLink {
	page: string;
	title: string;
	description: string;
	app: boolean;
	href: string | null;
	target: string | null;
}

export interface NavSection {
	title: string;
	links: NavLink[];
}

export interface SiteLink {
	page: string;
	title: string;
	href: string;
}

export interface Boot {
	site_name: string;
	socketio_port: number | null;
	/** False where the site turned socket.io off (disable_async), as the desk respects too. */
	realtime: boolean;
	user: { name: string; full_name: string; image: string | null; is_staff: boolean };
	person: string | null;
	/** "The Wilson Family", for a member in a Family. */
	household: string | null;
	church: { name: string; title: string; abbreviation: string | null; logo: string | null } | null;
	lang: string;
	rtl: boolean;
	translations: Record<string, string>;
	date_format: string;
	time_format: string;
	first_day_of_the_week: string;
	currency: string;
	/** The church's accent, already readable for each theme. */
	accent: { light: string; dark: string };
	/** enabled: the church uses self check-in (a steady rule); open: a Function is open for it now. */
	check_in: { enabled: boolean; open: boolean };
	push_public_key: string | null;
	offer_app_install: boolean;
	website_home: string | null;
	/** The Introduction of each replaced member web form, by route, as sanitized HTML. */
	intros: Record<string, string>;
	navigation: NavSection[];
	site_links: SiteLink[];
	hidden_pages: string[];
}

declare global {
	interface Window {
		churchit: Boot;
		csrf_token?: string;
	}
}

export const boot: Boot = window.churchit;

/** Whether *page* (an old route such as "household") is switched off or hidden for this member,
 * matching whole route segments as church_website.pages.is_page_off does. */
export function isPageHidden(page: string): boolean {
	const route = page.replace(/^\/+|\/+$/g, "").toLowerCase();
	return boot.hidden_pages.some((hidden) => route === hidden || route.startsWith(hidden + "/"));
}
