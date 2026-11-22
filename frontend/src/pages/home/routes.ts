import type { RouteRecordRaw } from "vue-router";

import { __ } from "@/translate";

const routes: RouteRecordRaw[] = [
	{ path: "/", component: () => import("@/pages/home/HomePage.vue"), meta: { title: __("This week") } },
];

export default routes;
