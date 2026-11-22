<template>
	<div class="mt-4 border-t border-outline-gray-1 pt-4">
		<LoadState :resource="thread" v-slot="{ data }">
			<ul v-if="data.comments.length" class="divide-y divide-outline-gray-1">
				<li
					v-for="item in data.comments"
					:key="item.name"
					class="py-3"
					:class="isFresh(item.name) && 'is-fresh'"
				>
					<p class="text-lg-medium text-ink-gray-9 md:text-md-medium">
						{{ item.comment_by }}
						<span class="text-ink-gray-6">{{ item.date_display }}</span>
					</p>
					<p class="mt-1 whitespace-pre-line text-p-lg text-ink-gray-8">
						{{ item.content }}
					</p>
				</li>
			</ul>
			<p v-else class="t-dateline text-ink-gray-6">{{ __("No comments yet.") }}</p>
			<form class="mt-4" @submit.prevent="post">
				<FormControl
					v-model="comment"
					type="textarea"
					:rows="3"
					size="lg"
					:label="__('Add a comment')"
					:description="__('Links are not allowed.')"
				/>
				<Button
					class="mt-3 min-h-11"
					size="lg"
					variant="solid"
					type="submit"
					:loading="commenting.loading"
					:disabled="!comment.trim()"
					:label="__('Comment')"
				/>
			</form>
		</LoadState>
	</div>
</template>

<script setup lang="ts">
import { __ } from "@/translate";
import { Button, FormControl, toast } from "frappe-ui";
import { ref } from "vue";

import { useAction, useRead } from "@/api";
import LoadState from "@/components/LoadState.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import type { PrayerComment } from "./types";

const props = defineProps<{
	page: "prayer-request" | "alms-request";
	name: string;
	topic: "prayer" | "alms";
}>();

type Thread = { comments: PrayerComment[] };
type Params = { page: string; name: string };

const thread = useRead<Thread, Params>("care.get_request_comments", {
	params: { page: props.page, name: props.name },
});
const commenting = useAction<Thread, Params & { comment: string }>("care.add_request_comment");
const { mark, isFresh } = useFreshInk();
const comment = ref("");

async function post() {
	await commenting.submit({ page: props.page, name: props.name, comment: comment.value }).then(
		() => {
			comment.value = "";
			toast.success(__("Comment added."));
			thread.reload();
		},
		() => {}
	);
}

useLiveRefresh([props.topic], async (hint) => {
	if (hint?.name && hint.name !== props.name) return;
	const known = new Set(thread.data?.comments.map((item) => item.name));
	await thread.reload();
	thread.data?.comments
		.filter((item) => !known.has(item.name))
		.forEach((item) => mark(item.name));
});
</script>
