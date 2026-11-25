<template>
	<!-- A date set like the margin of a diary: the numeral, then the weekday and month in spaced capitals. -->
	<div
		class="flex shrink-0 flex-col items-center text-center"
		:class="size === 'lg' ? 'w-20' : 'w-14'"
	>
		<span
			class="t-numeral"
			:class="[
				size === 'lg' ? 'text-[56px]' : 'text-[36px]',
				accent ? 'text-accent' : 'text-ink-gray-9',
			]"
		>
			{{ parts.day }}
		</span>
		<span class="t-label mt-2 text-ink-gray-7">{{ parts.weekday }}</span>
		<span class="t-label mt-0.5 text-ink-gray-6">{{ parts.month }}</span>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { boot } from "@/boot";

const props = withDefaults(
	defineProps<{ date: string; size?: "md" | "lg"; accent?: boolean }>(),
	{
		size: "md",
	},
);

const parts = computed(() => {
	const [year, month, day] = props.date.slice(0, 10).split("-").map(Number);
	const value = new Date(year, month - 1, day);
	return {
		day: value.getDate(),
		weekday: value.toLocaleDateString(boot.lang, { weekday: "short" }),
		month: value.toLocaleDateString(boot.lang, { month: "short" }),
	};
});
</script>
