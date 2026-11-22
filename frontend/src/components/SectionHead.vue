<template>
	<div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 pb-3">
		<component :is="`h${level}`" :id="id" class="t-head text-ink-gray-9">{{
			title
		}}</component>
		<p v-if="note" class="text-lg text-ink-gray-6 md:text-md">{{ note }}</p>
		<slot />
	</div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ title: string; note?: string; id?: string; level?: 2 | 3 }>(), {
	level: 2,
});
</script>
