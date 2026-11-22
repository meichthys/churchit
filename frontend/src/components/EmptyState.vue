<template>
	<!-- A blank space in the bulletin: a short rule, one quiet line, one plain sentence that says how the
	     space fills, and at most one action. No illustration, no icon tile. -->
	<div class="border-t border-outline-gray-1 px-4 py-10 text-center md:py-12">
		<span class="mx-auto block w-8 border-t border-ink-gray-3" aria-hidden="true" />
		<p class="t-dateline is-large mt-5 text-ink-gray-8">{{ title }}</p>
		<p v-if="body" class="mx-auto mt-2 max-w-[30rem] text-p-lg text-ink-gray-6">{{ body }}</p>
		<div v-if="$slots.default" class="mt-5 flex flex-wrap justify-center gap-2">
			<slot />
		</div>
	</div>
</template>

<script setup lang="ts">
defineProps<{ title: string; body?: string }>();
</script>
