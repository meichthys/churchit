<template>
	<PageHead :crumbs="[{ label: __('Prayer') }, { label: __('Prayer list') }]">
		<template #actions>
			<Button
				variant="outline"
				icon-left="lucide-heart"
				:label="__('My requests')"
				route="/prayer-request"
			/>
			<Button
				variant="solid"
				icon-left="lucide-plus"
				:label="__('Share a request')"
				route="/prayer-request/new"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('Prayer list')"
			:label="boot.church?.title"
			:dateline="__('Requests the church shares. Pray, then tap I prayed.')"
		/>

		<LoadState :resource="requests" v-slot="{ data }">
			<div class="mt-8 grid gap-10 md:grid-cols-12">
				<section class="md:col-span-8">
					<ul
						v-if="data.items.length"
						class="divide-y divide-outline-gray-1 border-y border-outline-gray-1"
					>
						<li
							v-for="item in data.items"
							:key="item.name"
							class="rounded-4 py-6"
							:class="isFresh(item.name) && 'is-fresh'"
						>
							<p
								v-if="item.urgent || item.visibility === 'Prayer Team'"
								class="t-label mb-2 flex flex-wrap gap-x-4"
							>
								<span v-if="item.urgent" class="text-ink-red-8">{{
									__("Urgent")
								}}</span>
								<span
									v-if="item.visibility === 'Prayer Team'"
									class="text-ink-gray-7"
									>{{ __("Prayer team only") }}</span
								>
							</p>
							<RouterLink
								:to="`/community-prayer-requests/${item.name}`"
								class="block"
							>
								<h2 class="t-subhead text-ink-gray-9">{{ item.title }}</h2>
							</RouterLink>
							<Facts
								:facts="[
									item.recipient_name
										? __('For {0}', [item.recipient_name])
										: null,
									item.type,
									item.date_display,
								]"
								class="mt-1 text-lg text-ink-gray-6 md:text-md"
							/>
							<p
								v-if="item.request"
								class="mt-3 line-clamp-4 whitespace-pre-line text-p-lg text-ink-gray-8"
							>
								{{ item.request }}
							</p>
							<div
								class="mt-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-2"
							>
								<PrayButton :request="item" @prayed="requests.reload()" />
								<RouterLink
									:to="`/community-prayer-requests/${item.name}`"
									class="min-h-11 content-center text-p-lg text-ink-gray-7 underline underline-offset-2 md:text-p-base"
								>
									{{ __("Read and comment") }}
								</RouterLink>
							</div>
						</li>
					</ul>
					<EmptyState
						v-else
						:title="__('No requests to pray for right now')"
						:body="__('A request shared with the whole church shows here.')"
					>
						<Button
							variant="solid"
							size="lg"
							icon-left="lucide-plus"
							:label="__('Share a request')"
							route="/prayer-request/new"
						/>
					</EmptyState>
				</section>
				<aside class="md:col-span-4 md:border-s md:border-outline-gray-1 md:ps-10">
					<SectionHead :title="__('Your own')" />
					<p class="mt-3 text-p-lg text-ink-gray-7 md:text-p-base">
						{{
							__("Ask the church to pray for you, your family or someone you know.")
						}}
					</p>
					<Button
						class="mt-4 min-h-11 w-full md:w-auto"
						size="lg"
						variant="outline"
						:label="__('Share a request')"
						route="/prayer-request/new"
					/>
				</aside>
			</div>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { RouterLink } from "vue-router";

import { useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import Facts from "@/components/Facts.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import PrayButton from "./PrayButton.vue";
import type { PrayerRequest } from "./types";

const requests = useRead<{ items: PrayerRequest[] }>("care.get_community_requests");
const { mark, isFresh } = useFreshInk();

useLiveRefresh(["prayer"], async (hint) => {
	await requests.reload();
	if (hint?.name) mark(hint.name);
});
</script>
