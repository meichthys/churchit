<template>
	<!-- A row of an index page: a date or icon in front, the title in Inter, its facts, how it stands, and a
	     chevron when the row opens a page. Rows are divided by hairlines (put them in a list with divide-y). -->
	<ItemListRow
		:as="route ? RouterLink : href ? 'a' : 'div'"
		v-bind="route ? { to: route } : href ? { href } : {}"
		size="lg"
		class="-mx-3 min-h-14 rounded-4 px-3 py-4"
		:class="[(route || href) && 'hover:bg-surface-gray-1', fresh && 'is-fresh']"
	>
		<template v-if="$slots.prefix" #prefix>
			<slot name="prefix" />
		</template>
		<div class="min-w-0 py-0.5">
			<p class="text-xl-medium text-ink-gray-9">{{ title }}</p>
			<Facts
				v-if="facts?.length || status"
				:facts="facts || []"
				class="mt-1 text-lg text-ink-gray-6 md:text-md"
			>
				<StatusBadge v-if="status" :status="status" class="mt-1.5 md:ms-1 md:mt-0" />
			</Facts>
			<slot />
		</div>
		<template v-if="$slots.suffix || route || href" #suffix>
			<slot name="suffix">
				<span
					class="size-5 text-ink-gray-5"
					:class="
						href
							? 'lucide-arrow-up-right rtl:-scale-x-100'
							: 'lucide-chevron-right rtl:-scale-x-100'
					"
					aria-hidden="true"
				/>
			</slot>
		</template>
	</ItemListRow>
</template>

<script setup lang="ts">
import { ItemListRow } from "frappe-ui";
import { RouterLink } from "vue-router";

import Facts from "@/components/Facts.vue";
import StatusBadge from "@/components/StatusBadge.vue";

defineProps<{
	title: string;
	route?: string;
	href?: string;
	facts?: (string | null | undefined)[];
	status?: string | null;
	fresh?: boolean;
}>();
</script>
