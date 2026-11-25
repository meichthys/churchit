<template>
	<PageHead
		:crumbs="[
			{ label: __('Sign-Ups'), route: '/function-sign-up' },
			{ label: __('Change sign-up') },
		]"
		:back="`/function-sign-up/${name}`"
	/>
	<PageBody>
		<LoadState :resource="detail" v-slot="{ data }">
			<Masthead
				:title="data.function_name"
				:label="boot.church?.title"
				:dateline="data.date_long"
			/>
			<SignUpForm
				v-if="data.can_edit"
				:items="data.items"
				:attending="data.attending"
				:notes="data.notes"
				:submit-label="__('Save changes')"
				:cancel-route="`/function-sign-up/${name}`"
				:busy="update.loading"
				@submit="save"
			/>
			<EmptyState
				v-else
				:title="__('This sign-up cannot be changed here')"
				:body="
					__(
						'It may be cancelled, closed, or made for you by the church office.',
					)
				"
			>
				<Button
					size="lg"
					class="min-h-11"
					:label="__('Back to the sign-up')"
					:route="`/function-sign-up/${name}`"
				/>
			</EmptyState>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button, toast } from "frappe-ui";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAction, useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import { __ } from "@/translate";

import SignUpForm from "./SignUpForm.vue";
import type { SignUpDetail } from "./types";

interface SaveParams {
	name: string;
	attending: boolean;
	notes: string;
	items: { item: string; my_quantity: number }[];
}

const route = useRoute();
const router = useRouter();
const name = computed(() => String(route.params.name));

const detail = useRead<SignUpDetail, { name: string }>("events.get_sign_up", {
	params: () => ({ name: name.value }),
});
const update = useAction<unknown, SaveParams>("events.update_sign_up");

async function save(value: {
	attending: boolean;
	notes: string;
	items: { item: string; my_quantity: number }[];
}) {
	const result = await update
		.submit({ name: name.value, ...value })
		.catch(() => null);
	if (!result) return;
	toast.success(__("Your changes are saved."));
	router.replace(`/function-sign-up/${name.value}`);
}
</script>
