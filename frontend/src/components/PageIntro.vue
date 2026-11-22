<template>
	<!-- The church's own words above a page that replaced a member web form: the form's Introduction, which
	     staff edit on the Web Form in the desk. The server sanitizes it. -->
	<div
		v-if="html"
		class="mt-5 max-w-[42rem] text-p-lg text-ink-gray-7 [&_a]:underline [&_a]:underline-offset-4 [&_p+p]:mt-3"
		v-html="html"
	/>
</template>

<script setup lang="ts">
import { boot } from "@/boot";

const props = defineProps<{ page: string }>();
const html = boot.intros?.[props.page] || "";
</script>
