<template>
	<div v-if="assignment.schedule.length || assignment.need_notes.length">
		<Button
			variant="ghost"
			size="lg"
			class="-ms-2 min-h-11"
			:label="open ? __('Hide the schedule') : __('Show the schedule')"
			:icon-left="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
			:aria-expanded="open"
			@click="open = !open"
		/>
		<ul v-if="open" class="mt-1 divide-y divide-outline-gray-1 border-t border-outline-gray-1">
			<li
				v-for="note in assignment.need_notes"
				:key="note.position"
				class="py-3 text-lg md:text-md"
			>
				<p class="text-ink-gray-6">{{ __("Note for {0}", [note.position]) }}</p>
				<p class="mt-0.5 whitespace-pre-line text-ink-gray-9">{{ note.notes }}</p>
			</li>
			<li
				v-for="(item, index) in assignment.schedule"
				:key="index"
				class="flex gap-4 py-3 text-lg md:text-md"
			>
				<bdi class="w-20 shrink-0 text-ink-gray-6">{{ item.time }}</bdi>
				<div class="min-w-0">
					<p
						:class="
							item.is_header ? 'font-semibold text-ink-gray-9' : 'text-ink-gray-9'
						"
					>
						{{ item.title }}
					</p>
					<p v-if="item.arrangement || item.key" class="text-ink-gray-6">
						{{
							[item.arrangement, item.key ? __("Key of {0}", [item.key]) : null]
								.filter(Boolean)
								.join(" · ")
						}}
					</p>
					<p v-if="item.detail" class="text-ink-gray-6">{{ item.detail }}</p>
					<p v-if="item.notes" class="whitespace-pre-line text-ink-gray-6">
						{{ item.notes }}
					</p>
					<p v-if="item.media.length" class="mt-1 flex flex-wrap gap-x-4">
						<a
							v-for="media in item.media"
							:key="media.url"
							:href="media.url"
							class="text-ink-gray-9 underline underline-offset-4"
						>
							{{ media.label }}
						</a>
					</p>
				</div>
			</li>
		</ul>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { ref } from "vue";

import type { Assignment } from "./types";

defineProps<{ assignment: Assignment }>();
const open = ref(false);
</script>
