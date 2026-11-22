<template>
	<PageHead :crumbs="[{ label: __('Directory') }]" />
	<PageBody>
		<Masthead
			:title="__('Directory')"
			:label="boot.church?.title"
			:dateline="__('Members of the church, with the details each one shares')"
		/>

		<LoadState :resource="directory" v-slot="{ data }">
			<EmptyState
				v-if="data.status === 'not_member'"
				:title="__('The directory is for members')"
				:body="__('Ask the church office if you would like to be listed.')"
			/>
			<template v-else>
				<div class="mt-6">
					<FormControl
						v-model="search"
						type="search"
						size="lg"
						:label="__('Search by name')"
						:placeholder="__('Type a name')"
					/>
				</div>
				<ul
					v-if="shown.length"
					class="mt-6 divide-y divide-outline-gray-1 border-y border-outline-gray-1"
				>
					<li v-for="entry in shown" :key="entry.name" class="flex gap-4 py-5">
						<Avatar
							:label="entry.title"
							:image="entry.photo || undefined"
							size="2xl"
							class="mt-0.5 shrink-0"
						/>
						<div class="min-w-0 flex-1">
							<h2 class="text-xl-medium text-ink-gray-9">{{ entry.title }}</h2>
							<ul class="mt-1 space-y-1 text-lg text-ink-gray-7 md:text-md">
								<li v-for="email in entry.emails" :key="email" class="break-words">
									<a
										:href="`mailto:${email}`"
										class="inline-flex min-h-11 items-center underline underline-offset-2 md:min-h-0"
										>{{ email }}</a
									>
								</li>
								<li v-for="phone in entry.phones" :key="phone">
									<a
										:href="`tel:${phone}`"
										class="inline-flex min-h-11 items-center underline underline-offset-2 md:min-h-0"
										><bdi>{{ phone }}</bdi></a
									>
								</li>
								<li
									v-for="address in entry.addresses"
									:key="address"
									class="text-ink-gray-6"
								>
									{{ address }}
								</li>
								<li v-if="entry.birthdays.length" class="text-ink-gray-6">
									{{ __("Birthday: {0}", [entry.birthdays.join(", ")]) }}
								</li>
							</ul>
							<a
								:href="`data:text/vcard;charset=utf-8,${encodeURIComponent(
									entry.vcard
								)}`"
								:download="contactFile(entry)"
								class="mt-2 inline-flex min-h-11 items-center gap-2 rounded-4 border border-outline-gray-2 px-4 text-p-lg text-ink-gray-8 hover:bg-surface-gray-1 md:min-h-0 md:py-1.5 md:text-p-base"
							>
								<span class="lucide-download size-4" aria-hidden="true" />{{
									__("Save contact")
								}}
							</a>
						</div>
					</li>
				</ul>
				<EmptyState
					v-else-if="search.trim()"
					:title="__('No one found')"
					:body="__('Try another spelling, or clear the search.')"
				/>
				<EmptyState
					v-else
					:title="__('No one is listed yet')"
					:body="__('Members who share their details appear here.')"
				/>
			</template>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Avatar, Button, FormControl } from "frappe-ui";
import { computed, ref } from "vue";

import { useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";

interface Entry {
	name: string;
	title: string;
	photo: string | null;
	emails: string[];
	phones: string[];
	addresses: string[];
	birthdays: string[];
	vcard: string;
	search: string;
}

const directory = useRead<{ status: "ok" | "not_member"; entries: Entry[] }>(
	"directory.get_directory"
);
const search = ref("");

const shown = computed(() => {
	const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
	const entries = directory.data?.entries || [];
	return words.length
		? entries.filter((entry) => words.every((word) => entry.search.includes(word)))
		: entries;
});

function contactFile(entry: Entry): string {
	return `${entry.title.replace(/[^\p{L}\p{N}]+/gu, "-")}.vcf`;
}
</script>
