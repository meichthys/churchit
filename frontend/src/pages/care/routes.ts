import type { RouteRecordRaw } from "vue-router";

import { __ } from "@/translate";

const routes: RouteRecordRaw[] = [
	{ path: "/directory", component: () => import("./DirectoryPage.vue"), meta: { page: "directory", title: __("Directory") } },
	{ path: "/prayer-request/:rest(.*)*", component: () => import("./PrayerRequestsPage.vue"), meta: { page: "prayer-request", title: __("My Prayer Requests") } },
	{ path: "/community-prayer-requests", component: () => import("./CommunityPrayerPage.vue"), meta: { page: "community-prayer-requests", title: __("Prayer List") } },
	{ path: "/community-prayer-requests/list", redirect: "/community-prayer-requests" },
	{ path: "/community-prayer-requests/:name", component: () => import("./CommunityPrayerDetailPage.vue"), meta: { page: "community-prayer-requests", title: __("Prayer List") } },
	{ path: "/care-request/:rest(.*)*", component: () => import("./CareRequestsPage.vue"), meta: { page: "care-request", title: __("Care Requests") } },
	{ path: "/alms-request/:rest(.*)*", component: () => import("./AlmsRequestsPage.vue"), meta: { page: "alms-request", title: __("Benevolence Requests") } },
];

export default routes;
