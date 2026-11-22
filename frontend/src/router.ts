import { shellScrollContainer } from "frappe-ui";
import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import { boot, isPageHidden } from "./boot";
import { __ } from "./translate";

/** Each area of the app declares its routes in pages/<area>/routes.ts. A route's meta.page is the old
 * route of its page ("household"): a page this member must not see shows Not Found, as the old route did. */
const areaRoutes = import.meta.glob<{ default: RouteRecordRaw[] }>("./pages/*/routes.ts", { eager: true });

declare module "vue-router" {
	interface RouteMeta {
		page?: string;
		title?: string;
	}
}

const router = createRouter({
	history: createWebHistory("/portal"),
	routes: [
		...Object.values(areaRoutes).flatMap((module) => module.default),
		{ path: "/:path(.*)*", name: "not-found", component: () => import("./pages/NotFound.vue") },
	],
});

router.beforeEach((to) => {
	if (to.name !== "not-found" && to.meta.page && isPageHidden(to.meta.page)) {
		return { name: "not-found", params: { path: to.path.slice(1).split("/") }, query: to.query, hash: to.hash };
	}
});

router.afterEach((to) => {
	const church = boot.church?.title;
	document.title = [to.meta.title, church].filter(Boolean).join(" · ") || __("Member Portal");
	if (!to.hash) shellScrollContainer.value?.scrollTo({ top: 0 });
});

// A deploy removes the old route chunks; an open tab then loads the new build once instead of failing.
const RELOADED = "churchit-portal-reloaded";
function reloadOnce(path: string) {
	if (sessionStorage.getItem(RELOADED) === path) return;
	sessionStorage.setItem(RELOADED, path);
	window.location.assign(path);
}
router.onError((error, to) => {
	if (/dynamically imported module|Importing a module script failed/i.test(String(error?.message))) {
		reloadOnce(router.resolve(to).href);
	}
});
window.addEventListener("vite:preloadError", () => reloadOnce(window.location.pathname + window.location.search));

export default router;
