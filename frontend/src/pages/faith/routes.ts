import type { RouteRecordRaw } from "vue-router";

import { __ } from "@/translate";

const routes: RouteRecordRaw[] = [
	{ path: "/memorize", component: () => import("@/pages/faith/Memorize.vue"), meta: { page: "memorize", title: __("Bible Memory") } },
	{
		// The old practice page: /memorize/session?item=X&mode=type.
		path: "/memorize/session",
		redirect: (to) => ({ path: `/memorize/${to.query.item || ""}`, query: { mode: to.query.mode } }),
		meta: { page: "memorize", title: __("Bible Memory") },
	},
	{ path: "/memorize/:item", component: () => import("@/pages/faith/Practice.vue"), meta: { page: "memorize", title: __("Practice") } },
	{ path: "/bible", component: () => import("@/pages/faith/Bible.vue"), meta: { page: "bible", title: __("Bible") } },
	{ path: "/bulletins", component: () => import("@/pages/faith/Bulletins.vue"), meta: { page: "bulletins", title: __("Bulletins") } },
];

export default routes;
