<template>
	<!-- A form or a choice over the page: a BottomSheet on phones, a Dialog on desktop. Put the fields in the
	     default slot and the buttons in #actions; the sheet stacks them full width for the thumb. -->
	<BottomSheet
		v-if="isMobile"
		v-model:open="open"
		:title="title"
		:dismissible="dismissible"
	>
		<div class="px-5 pb-6">
			<p v-if="description" class="mb-4 text-p-lg text-ink-gray-6">
				{{ description }}
			</p>
			<slot />
			<div
				v-if="$slots.actions"
				class="mt-6 flex flex-col-reverse gap-2 [&>*]:min-h-11 [&>*]:w-full"
			>
				<slot name="actions" />
			</div>
		</div>
	</BottomSheet>
	<Dialog
		v-else
		v-model:open="open"
		:title="title"
		:dismissible="dismissible"
	>
		<p v-if="description" class="mb-4 text-p-base text-ink-gray-6">
			{{ description }}
		</p>
		<slot />
		<template v-if="$slots.actions" #actions>
			<div class="flex flex-wrap justify-end gap-2">
				<slot name="actions" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { BottomSheet, Dialog } from "frappe-ui";

import { useIsMobile } from "@/layouts/useIsMobile";

withDefaults(
	defineProps<{
		title: string;
		description?: string;
		dismissible?: boolean;
	}>(),
	{
		dismissible: true,
	},
);
const open = defineModel<boolean>("open", { default: false });
const isMobile = useIsMobile();
</script>
