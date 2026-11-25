<template>
	<!-- "9:45 AM" with the day period set smaller, in the site's 12 or 24 hour clock. <bdi> keeps it whole in right-to-left text. -->
	<bdi class="tabular-nums">
		<template v-for="(part, index) in parts" :key="index">
			<span
				v-if="part.type === 'dayPeriod'"
				class="text-md font-medium text-ink-gray-6 md:text-sm"
				>{{ part.value }}</span
			>
			<template v-else>{{ part.value }}</template>
		</template>
	</bdi>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { boot } from "@/boot";

/** value: "HH:mm:ss", or a "YYYY-MM-DD HH:mm:ss" datetime. */
const props = defineProps<{ value: string }>();

const parts = computed(() => {
	const time = props.value.includes(" ")
		? props.value.split(" ")[1]
		: props.value;
	const [hour, minute] = time.split(":").map(Number);
	const date = new Date(2000, 0, 1, hour, minute);
	return new Intl.DateTimeFormat(boot.lang, {
		hour: "numeric",
		minute: "2-digit",
		hour12: !/^HH/.test(boot.time_format),
	}).formatToParts(date);
});
</script>
