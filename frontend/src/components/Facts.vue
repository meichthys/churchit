<template>
	<!-- Short facts: one per line on phones (no separator left hanging), joined with a dot on wider screens. -->
	<p class="md:flex md:flex-wrap md:items-baseline md:gap-x-2">
		<template v-for="(fact, index) in shown" :key="index">
			<span
				v-if="index"
				class="hidden text-ink-gray-4 md:inline"
				aria-hidden="true"
				>·</span
			>
			<span class="block md:inline">{{ fact }}</span>
		</template>
		<slot />
	</p>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ facts: (string | null | undefined)[] }>();
const shown = computed(() =>
	props.facts.filter((fact): fact is string => Boolean(fact)),
);
</script>
