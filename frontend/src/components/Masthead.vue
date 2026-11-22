<template>
	<!-- The masthead: a serif title, an italic dateline and the thick-thin rule of a printed bulletin.
	     Phones drop the label above the title, so the first screen is not spent on headings. -->
	<header class="pb-2">
		<p v-if="label" class="t-label hidden text-ink-gray-6 md:block">{{ label }}</p>
		<div class="flex flex-wrap items-end justify-between gap-x-10 gap-y-3 md:mt-3">
			<h1 class="t-title text-ink-gray-9">{{ title }}</h1>
			<slot name="aside" />
		</div>
		<p v-if="dateline" class="t-dateline mt-2 text-ink-gray-6">{{ dateline }}</p>
		<div class="rule-double mt-4 md:mt-6" />
		<slot />
	</header>
</template>

<script setup lang="ts">
defineProps<{ title: string; label?: string; dateline?: string }>();
</script>
