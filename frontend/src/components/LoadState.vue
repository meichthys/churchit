<template>
	<!-- What a page shows around a read: quiet lines while it first loads, a plain message with Try again when
	     it fails, and the page itself once the data is there (a reload keeps the page on screen). -->
	<div
		v-if="resource.error && !resource.data"
		class="border-t border-outline-gray-1 py-10 text-center"
		role="alert"
	>
		<p class="t-dateline is-large text-ink-gray-8">{{ __("This did not load") }}</p>
		<p class="mx-auto mt-2 max-w-[30rem] text-p-lg text-ink-gray-6">
			{{ errorText(resource.error) }}
		</p>
		<Button
			class="mt-5 min-h-11"
			size="lg"
			:label="__('Try again')"
			@click="resource.reload()"
		/>
	</div>
	<div
		v-else-if="!resource.data"
		class="space-y-4 py-6"
		:aria-label="__('Loading')"
		aria-busy="true"
	>
		<div
			v-for="line in lines"
			:key="line"
			class="h-5 animate-pulse rounded-4 bg-surface-gray-2"
			:style="{ width: `${90 - line * 12}%` }"
		/>
	</div>
	<slot v-else :data="resource.data" />
</template>

<script setup lang="ts" generic="T">
import { Button } from "frappe-ui";

import { errorText } from "@/api";

withDefaults(
	defineProps<{
		resource: {
			data: T | null | undefined;
			error: unknown;
			loading: boolean;
			reload: () => unknown;
		};
		lines?: number;
	}>(),
	{ lines: 4 }
);

defineSlots<{ default(props: { data: T }): unknown }>();
</script>
