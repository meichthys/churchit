<template>
	<!-- One line of a programme: time | item ........ who. Under it the facts, how it stands, and any action.
	     The title link's inline padding gives it a 44px tap area on phones without moving the line. -->
	<div
		class="grid grid-cols-[4.75rem_minmax(0,1fr)] gap-x-3 md:grid-cols-[5.5rem_minmax(0,1fr)] md:gap-x-4"
		:class="fresh && 'is-fresh -mx-3 rounded-4 px-3 py-2'"
	>
		<p
			class="pt-px text-lg font-medium text-ink-gray-8"
			:class="dimTime && 'text-ink-gray-5'"
		>
			<TimeText v-if="time" :value="time" />
		</p>

		<div class="min-w-0">
			<div
				class="flex flex-wrap items-baseline gap-x-3 md:flex-nowrap md:gap-x-0"
			>
				<RouterLink
					v-if="route"
					:to="route"
					class="py-3 text-xl-medium text-ink-gray-9 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-ink-gray-7 md:py-0"
				>
					{{ title }}
				</RouterLink>
				<a
					v-else-if="href"
					:href="href"
					class="py-3 text-xl-medium text-ink-gray-9 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-ink-gray-7 md:py-0"
				>
					{{ title }}
				</a>
				<span v-else class="text-xl-medium text-ink-gray-9">{{
					title
				}}</span>
				<template v-if="who">
					<span class="leader hidden md:block" aria-hidden="true" />
					<span
						class="t-label ms-auto shrink-0 text-ink-gray-7 md:ms-0"
						>{{ who }}</span
					>
				</template>
			</div>

			<Facts
				v-if="facts?.length || status"
				:facts="facts || []"
				class="mt-1 text-lg text-ink-gray-6"
			>
				<StatusBadge
					v-if="status"
					:status="status"
					class="mt-1.5 md:ms-1 md:mt-0"
				/>
			</Facts>

			<div v-if="$slots.default" class="mt-3">
				<slot />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import Facts from "@/components/Facts.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import TimeText from "@/components/TimeText.vue";

defineProps<{
	title: string;
	/** "HH:mm:ss" or a datetime; leave empty for an entry without a time. */
	time?: string | null;
	/** Set a repeated time quietly instead of leaving it out. */
	dimTime?: boolean;
	route?: string;
	href?: string;
	/** Who is going or leading, in spaced capitals after the leader dots: "JAMES · SARAH". */
	who?: string;
	facts?: (string | null | undefined)[];
	status?: string | null;
	/** A live update just changed this entry. */
	fresh?: boolean;
}>();
</script>
