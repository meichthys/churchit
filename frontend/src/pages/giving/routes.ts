import type { RouteRecordRaw } from "vue-router";

import { __ } from "@/translate";

const routes: RouteRecordRaw[] = [
	{ path: "/pledge/:rest(.*)*", component: () => import("@/pages/giving/PledgesPage.vue"), meta: { page: "pledge", title: __("Pledges") } },
	{ path: "/statements", component: () => import("@/pages/giving/StatementsPage.vue"), meta: { page: "statements", title: __("Giving Statements") } },
];

export default routes;
