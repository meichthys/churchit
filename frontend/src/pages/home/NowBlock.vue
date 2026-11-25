<template>
	<!-- Check-in is open: the first thing on the page. -->
	<section class="mt-8 border-y border-outline-gray-3 py-6" aria-labelledby="now-head">
		<p class="t-label text-accent">{{ __("Now") }}</p>
		<h2 id="now-head" class="t-head mt-1 text-ink-gray-9">{{ __("Check-in is open") }}</h2>
		<ul class="mt-3 space-y-1">
			<li
				v-for="function_ in checkIn.functions"
				:key="function_.name"
				class="text-lg text-ink-gray-8"
			>
				<span class="font-medium">{{ function_.title }}</span>
				<template v-if="function_.time">
					<span class="text-ink-gray-5"> &middot; </span
					><TimeText :value="function_.time" />
				</template>
			</li>
		</ul>
		<Button
			class="mt-5 min-h-11 w-full md:w-auto"
			variant="solid"
			size="lg"
			route="/check-in"
			:label="label"
		/>
	</section>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed } from "vue";

import { boot } from "@/boot";
import TimeText from "@/components/TimeText.vue";
import { __ } from "@/translate";

import type { Home } from "./types";

const props = defineProps<{ checkIn: NonNullable<Home["check_in"]> }>();

const label = computed(() => {
	const names = props.checkIn.people.map((person) => person.display_name.split(" ")[0]);
	if (!names.length) return __("Open check-in");
	const list = new Intl.ListFormat(boot.lang, { style: "long", type: "conjunction" }).format(
		names
	);
	return __("Check in {0}", [list]);
});
</script>
