<template>
	<div>
		<p class="text-lg text-ink-gray-6 md:text-md">
			{{
				__(
					"See the functions you accepted in the calendar on your phone or computer. It keeps itself up to date.",
				)
			}}
		</p>
		<template v-if="calendar">
			<div class="mt-3 flex flex-wrap items-end gap-2">
				<a
					:href="calendar.webcal"
					class="inline-flex min-h-11 items-center rounded bg-surface-gray-7 px-4 text-base font-medium text-ink-white hover:bg-surface-gray-6"
				>
					{{ __("Subscribe") }}
				</a>
				<FormControl
					size="lg"
					:model-value="calendar.url"
					type="text"
					readonly
					class="min-w-0 flex-1 basis-56"
					:aria-label="__('Calendar link')"
					@focus="($event.target as HTMLInputElement).select()"
				/>
				<Button
					variant="outline"
					size="lg"
					class="min-h-11"
					:label="copied ? __('Copied') : __('Copy')"
					@click="copy(calendar.url)"
				/>
			</div>
			<p class="mt-3 text-lg text-ink-gray-6 md:text-md">
				{{
					__(
						"In Google Calendar, add the copied link under Other calendars, From URL. Anyone with the link can see where you serve.",
					)
				}}
			</p>
			<Button
				variant="ghost"
				size="lg"
				class="-ms-2 mt-1 min-h-11"
				:label="__('Stop this link and make a new one')"
				@click="confirmNewKey"
			/>
		</template>
		<Button
			v-else
			variant="outline"
			size="lg"
			class="mt-3 min-h-11"
			:label="__('Make a calendar link')"
			:loading="makeKey.loading"
			@click="makeNewKey"
		/>
	</div>
</template>

<script setup lang="ts">
import { Button, FormControl, dialog } from "frappe-ui";
import { ref } from "vue";

import { useFrappeAction } from "@/api";
import { __ } from "@/translate";

defineProps<{ calendar: { url: string; webcal: string } | null }>();
const emit = defineEmits<{ changed: [] }>();

const copied = ref(false);
const makeKey = useFrappeAction(
	"churchit.church_ministries.member_ministry_team.make_own_calendar_key",
);

async function makeNewKey() {
	await makeKey.submit().then(
		() => emit("changed"),
		() => {},
	);
}

function confirmNewKey() {
	dialog.confirm({
		title: __("Make a new calendar link"),
		message: __(
			"The old link stops working. Add the new link to your calendar again.",
		),
		confirmLabel: __("Make a new link"),
		cancelLabel: __("Cancel"),
		onConfirm: async ({ close }) => {
			await makeNewKey();
			close();
		},
	});
}

async function copy(url: string): Promise<void> {
	if (!navigator.clipboard) return;
	await navigator.clipboard.writeText(url);
	copied.value = true;
}
</script>
