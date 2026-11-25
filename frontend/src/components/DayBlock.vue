<template>
	<!-- One day of a running order. Desktop hangs the date in the margin; phones set it as a head above the entries. -->
	<article
		class="border-t border-outline-gray-1 py-5 md:grid md:grid-cols-[8rem_minmax(0,1fr)] md:gap-x-6"
		:class="compact ? 'md:py-5' : 'md:py-7'"
	>
		<div class="mb-4 flex items-end gap-3 md:mb-0 md:block">
			<span
				class="t-numeral"
				:class="[
					compact
						? 'text-[36px] md:text-[44px]'
						: 'text-[44px] md:text-[60px]',
					today ? 'text-accent' : 'text-ink-gray-9',
				]"
			>
				{{ parts.day }}
			</span>
			<div class="pb-0.5 md:mt-3">
				<p class="t-label text-ink-gray-7">{{ parts.weekday }}</p>
				<p
					class="t-label mt-0.5"
					:class="today ? 'text-accent' : 'text-ink-gray-6'"
				>
					{{ today ? __("Today") : parts.month }}
				</p>
			</div>
		</div>
		<div class="space-y-5">
			<slot />
		</div>
	</article>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { boot } from "@/boot";

const props = defineProps<{
	date: string;
	today?: boolean;
	compact?: boolean;
}>();

const parts = computed(() => {
	const [year, month, day] = props.date.slice(0, 10).split("-").map(Number);
	const value = new Date(year, month - 1, day);
	return {
		day: value.getDate(),
		weekday: value.toLocaleDateString(boot.lang, { weekday: "long" }),
		month: value.toLocaleDateString(boot.lang, { month: "long" }),
	};
});
</script>
