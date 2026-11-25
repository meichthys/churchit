import type { RouteLocationNormalizedLoaded } from "vue-router";

import { boot, isPageHidden, type NavLink, type SiteLink } from "./boot";
import { __ } from "./translate";

/** One menu entry, for the Sidebar, the phone tabs and the More sheet alike. */
export interface MenuItem {
	key: string;
	label: string;
	icon: string;
	/** An app route (same tab, through the router)... */
	route?: string;
	/** ...or a page of the website or another app (a full page load). */
	href?: string;
	target?: string;
	/** The routes that light this entry up, beyond its own. */
	match?: string[];
	open?: boolean;
}

export interface MenuSection {
	label: string;
	items: MenuItem[];
}

/** The icon of each page, by its old route. Tailwind draws only the lucide classes written out in full,
 * so the server sends no icon names. */
const ICONS: Record<string, string> = {
	"function-sign-up": "lucide-calendar-check",
	attendance: "lucide-clipboard-check",
	"ministry-team": "lucide-hand-helping",
	groups: "lucide-users-round",
	"group-leader": "lucide-user-round-cog",
	"group-files": "lucide-folder",
	directory: "lucide-book-user",
	"room-request": "lucide-door-open",
	"community-prayer-requests": "lucide-heart",
	"prayer-request": "lucide-message-circle-heart",
	"care-request": "lucide-hand-heart",
	"alms-request": "lucide-hand-coins",
	memorize: "lucide-book-marked",
	bible: "lucide-book-open",
	bulletins: "lucide-newspaper",
	pledge: "lucide-sprout",
	statements: "lucide-receipt-text",
	household: "lucide-house",
	"personal-details": "lucide-id-card",
	preferences: "lucide-sliders-horizontal",
	give: "lucide-gift",
	register: "lucide-calendar-plus",
	calendar: "lucide-calendar",
	sermons: "lucide-audio-lines",
	website: "lucide-globe",
	desk: "lucide-layout-dashboard",
};

export function iconFor(page: string): string {
	return ICONS[page] || "lucide-link";
}

function fromNavLink(link: NavLink): MenuItem {
	if (link.app) return { key: link.page, label: link.title, icon: iconFor(link.page), route: "/" + link.page };
	return {
		key: link.page || link.href || link.title,
		label: link.title,
		icon: iconFor(link.page),
		href: link.href || "/",
		target: link.target || undefined,
	};
}

function fromSiteLink(link: SiteLink): MenuItem {
	return { key: link.page, label: link.title, icon: iconFor(link.page), href: link.href };
}

export const thisWeek: MenuItem = { key: "home", label: __("This week"), icon: "lucide-calendar-days", route: "/" };

export const checkIn: MenuItem | null = boot.check_in.enabled
	? { key: "check-in", label: __("Check-in"), icon: "lucide-qr-code", route: "/check-in", open: boot.check_in.open }
	: null;

const give = boot.site_links.find((link) => link.page === "give");
const givingSection = boot.navigation.findIndex((section) =>
	section.links.some((link) => link.page === "pledge" || link.page === "statements"),
);

/** The member's menu: the Portal Settings rows this member may see, in the server's sections.
 * Give sits with Giving (or under Elsewhere when Giving shows nothing else). */
export const sections: MenuSection[] = boot.navigation.map((section, index) => ({
	label: section.title,
	items: [
		...(give && index === givingSection ? [fromSiteLink(give)] : []),
		...section.links.map(fromNavLink),
	],
}));

export const elsewhere: MenuItem[] = [
	...(give && givingSection < 0 ? [fromSiteLink(give)] : []),
	...boot.site_links.filter((link) => link.page !== "give").map(fromSiteLink),
	...(boot.website_home
		? [{ key: "website", label: __("Church website"), icon: iconFor("website"), href: boot.website_home }]
		: []),
	...(boot.user.is_staff ? [{ key: "desk", label: __("Desk"), icon: iconFor("desk"), href: "/desk" }] : []),
];

const allItems = sections.flatMap((section) => section.items);

/** The phone tabs: This week, Check-in (Sign-ups for a church without self check-in), Groups and Prayer.
 * The rule depends on the church, not the day, so the tabs never move under a member's thumb. */
export const tabs: MenuItem[] = [
	thisWeek,
	checkIn || asTab(findRoute("function-sign-up"), __("Sign-ups")),
	asTab(findRoute("groups"), __("Groups")),
	asTab(findRoute("community-prayer-requests") || findRoute("prayer-request"), __("Prayer")),
].filter((item): item is MenuItem => Boolean(item));

/** A tab takes a short label of its own; the menu row's title may be long ("Community Prayer Requests"). */
function asTab(item: MenuItem | undefined, label: string): MenuItem | undefined {
	return item && { ...item, label };
}

/** The More sheet: every entry that is not a tab, in menu order, then Elsewhere. */
export const moreSections: MenuSection[] = [
	...sections.map((section) => ({
		label: section.label,
		items: section.items.filter((item) => !tabs.some((tab) => tab.key === item.key)),
	})),
	{ label: __("Elsewhere"), items: elsewhere },
].filter((section) => section.items.length);

function findRoute(key: string): MenuItem | undefined {
	return allItems.find((item) => item.key === key && item.route);
}

/** Whether *item* is the page on screen: its own route or a path under it, or one of its match routes. */
export function isCurrent(item: MenuItem, route: RouteLocationNormalizedLoaded): boolean {
	if (!item.route) return false;
	return [item.route, ...(item.match || [])].some((path) =>
		path === "/" ? route.path === "/" : route.path === path || route.path.startsWith(path + "/"),
	);
}

export { isPageHidden };
