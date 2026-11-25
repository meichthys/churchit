<template>
	<PageHead
		:crumbs="[
			{ label: __('Prayer list'), route: '/community-prayer-requests' },
			{ label: request.data?.title || '' },
		]"
		back="/community-prayer-requests"
	/>
	<PageBody>
		<LoadState :resource="request" v-slot="{ data }">
			<Masthead
				:title="data.title"
				:label="boot.church?.title"
				:dateline="
					[
						data.recipient_name
							? __('For {0}', [data.recipient_name])
							: null,
						data.type,
						data.date_display,
					]
						.filter(Boolean)
						.join(' · ')
				"
			/>
			<div class="mt-8 grid gap-10 md:grid-cols-12">
				<section class="md:col-span-8">
					<p
						v-if="data.is_team_only"
						class="mb-5 flex items-start gap-2 text-p-lg text-ink-gray-8"
					>
						<span
							class="lucide-lock mt-1 size-5 shrink-0"
							aria-hidden="true"
						/>
						{{
							__(
								"Only the prayer team sees this request. Please keep it within the team.",
							)
						}}
					</p>
					<p v-if="data.urgent" class="t-label mb-3 text-ink-red-8">
						{{ __("Urgent") }}
					</p>
					<p
						v-if="data.request"
						class="whitespace-pre-line text-p-lg text-ink-gray-9"
					>
						{{ data.request }}
					</p>

					<div class="mt-8 border-t border-outline-gray-1 pt-6">
						<SectionHead :title="__('Pray for this request')" />
						<FormControl
							v-if="!data.prayed_today"
							v-model="note"
							class="mt-3"
							type="textarea"
							:rows="2"
							size="lg"
							:label="__('A note with your prayer (optional)')"
						/>
						<div class="mt-3">
							<PrayButton
								:request="data"
								:note="note"
								@prayed="onPrayed"
							/>
						</div>
					</div>

					<div class="mt-10 border-t border-outline-gray-1 pt-6">
						<SectionHead :title="__('Comments')" />
						<ul
							v-if="data.comments.length"
							class="mt-3 divide-y divide-outline-gray-1"
						>
							<li
								v-for="comment in data.comments"
								:key="comment.name"
								class="py-4"
								:class="isFresh(comment.name) && 'is-fresh'"
							>
								<p
									class="text-lg-medium text-ink-gray-9 md:text-md-medium"
								>
									{{ comment.comment_by }}
									<span class="text-ink-gray-6">{{
										comment.date_display
									}}</span>
								</p>
								<p
									class="mt-1 whitespace-pre-line text-p-lg text-ink-gray-8"
								>
									{{ comment.content }}
								</p>
							</li>
						</ul>
						<p v-else class="t-dateline mt-3 text-ink-gray-6">
							{{ __("No comments yet.") }}
						</p>
						<form class="mt-4" @submit.prevent="postComment">
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
					</div>
				</section>
				<aside
					class="md:col-span-4 md:border-s md:border-outline-gray-1 md:ps-10"
				>
					<Button
						class="min-h-11"
						size="lg"
						variant="outline"
						:label="__('Back to the prayer list')"
						route="/community-prayer-requests"
					>
						<template #prefix
							><span
								class="lucide-arrow-left size-4 rtl:-scale-x-100"
								aria-hidden="true"
						/></template>
					</Button>
				</aside>
			</div>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { __ } from "@/translate";
import { Button, FormControl, toast } from "frappe-ui";
import { ref } from "vue";
import { useRoute } from "vue-router";

import { useAction, useRead } from "@/api";
import { boot } from "@/boot";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import PrayButton from "./PrayButton.vue";
import type { PrayerComment, PrayerRequest } from "./types";

type Detail = PrayerRequest & {
	comments: PrayerComment[];
	is_team_only: boolean;
};

const route = useRoute();
const request = useRead<Detail, { name: string }>(
	"care.get_community_request",
	{
		params: { name: String(route.params.name) },
	},
);
const commenting = useAction<
	{ comments: PrayerComment[] },
	{ prayer_request: string; comment: string }
>("care.add_prayer_comment");
const { mark, isFresh } = useFreshInk();
const note = ref("");
const comment = ref("");

function onPrayed() {
	note.value = "";
	request.reload();
}

async function postComment() {
	await commenting
		.submit({
			prayer_request: String(route.params.name),
			comment: comment.value,
		})
		.then(
			() => {
				comment.value = "";
				toast.success(__("Comment added."));
				request.reload();
			},
			() => {},
		);
}

useLiveRefresh(["prayer"], async (hint) => {
	if (hint?.name && hint.name !== route.params.name) return;
	const known = new Set(request.data?.comments.map((item) => item.name));
	await request.reload();
	request.data?.comments
		.filter((item) => !known.has(item.name))
		.forEach((item) => mark(item.name));
});
</script>
