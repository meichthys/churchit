<template>
	<!-- One open group: what it is, and one button to join it or to ask its leaders. -->
	<IndexRow
		:title="group.group_name"
		:facts="[
			group.description,
			group.requires_approval
				? __('A leader approves new members.')
				: null,
		]"
	>
		<template #suffix>
			<Button
				size="lg"
				class="min-h-11"
				:label="
					group.requires_approval ? __('Ask to join') : __('Join')
				"
				:loading="join.loading"
				@click="send"
			/>
		</template>
	</IndexRow>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";

import { useFrappeAction } from "@/api";
import IndexRow from "@/components/IndexRow.vue";

import type { JoinableGroup } from "./types";
import { __ } from "@/translate";

const props = defineProps<{ group: JoinableGroup }>();
const emit = defineEmits<{ done: [] }>();

const join = useFrappeAction<
	{ requested?: boolean; joined?: boolean },
	Record<string, unknown>
>("churchit.church_people.group_api.join_group");

async function send() {
	const result = await join
		.submit({ group: props.group.name })
		.catch(() => null);
	if (!result) return;

	if (result.requested)
		toast.success(
			__("Your request to join {0} is with its leaders.", [
				props.group.group_name,
			]),
		);
	else toast.success(__("You joined {0}.", [props.group.group_name]));
	emit("done");
}
</script>
