import type { RouteRecordRaw } from "vue-router";

import { __ } from "@/translate";

const routes: RouteRecordRaw[] = [
	{ path: "/check-in", component: () => import("./CheckInPage.vue"), meta: { page: "household", title: __("Check-in") } },
	{ path: "/household", component: () => import("./HouseholdPage.vue"), meta: { page: "household", title: __("My Household") } },
	{
		path: "/personal-details/:rest(.*)*",
		component: () => import("./PersonalDetailsPage.vue"),
		meta: { page: "personal-details", title: __("My Details") },
	},
	{ path: "/preferences", component: () => import("./PreferencesPage.vue"), meta: { page: "preferences", title: __("Preferences") } },
];

export default routes;
