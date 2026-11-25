<template>
	<!-- The three views of what a member does at events: their sign-ups, what is open, and what they attended. -->
	<Tabs
		v-if="tabs.length > 1"
		:model-value="current"
		class="mt-6"
		@update:model-value="open"
	>
		<TabList variant="underline">
			<TabTrigger
				v-for="tab in tabs"
				:key="tab.value"
				:value="tab.value"
				:label="tab.label"
				class="min-h-11"
			/>
		</TabList>
	</Tabs>
</template>

<script setup lang="ts">
import { TabList, Tabs, TabTrigger } from "frappe-ui";
import { computed } from "vue";
import { useRouter } from "vue-router";

import { isPageHidden } from "@/boot";
import { __ } from "@/translate";

defineProps<{ current: "upcoming" | "open" | "attended" }>();

const router = useRouter();

const tabs = computed(() => [
	...(isPageHidden("function-sign-up")
		? []
		: [
				{ value: "upcoming", label: __("Upcoming") },
				{ value: "open", label: __("Open") },
			]),
	...(isPageHidden("attendance")
		? []
		: [{ value: "attended", label: __("Attended") }]),
]);

function open(tab: string | number) {
	if (tab === "attended") router.push("/attendance");
	else
		router.push({
			path: "/function-sign-up/list",
			query: tab === "open" ? { tab: "open" } : {},
		});
}
</script>
