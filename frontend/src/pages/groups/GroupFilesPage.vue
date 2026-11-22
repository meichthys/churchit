<template>
	<PageHead :crumbs="[{ label: __('Group files') }]">
		<template v-if="files.data?.can_add" #actions>
			<Button
				variant="solid"
				icon-left="lucide-plus"
				:label="__('Add a file')"
				@click="adding = true"
			/>
		</template>
	</PageHead>
	<PageBody>
		<Masthead
			:title="__('Group files')"
			:label="boot.church?.title"
			:dateline="__('Files shared in your groups')"
		/>
		<LoadState :resource="files" v-slot="{ data }">
			<section class="mt-8" aria-labelledby="files-list">
				<SectionHead
					id="files-list"
					:title="__('Files')"
					:note="
						data.can_add
							? undefined
							: __('Only the leaders of a group can add a file to it.')
					"
				>
					<Button
						v-if="data.can_add && data.items.length"
						class="min-h-11 md:hidden"
						variant="subtle"
						size="lg"
						icon-left="lucide-plus"
						:label="__('Add a file')"
						@click="adding = true"
					/>
				</SectionHead>
				<ul
					v-if="data.items.length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="file in data.items" :key="file.name">
						<IndexRow
							:title="file.title"
							:href="file.file_url"
							:facts="[file.group_name, __('Added {0}', [file.added_on])]"
							:fresh="isFresh(file.name)"
						>
							<template #prefix
								><span
									class="lucide-file-text size-6 shrink-0 text-ink-gray-5"
									aria-hidden="true"
							/></template>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('No files yet')"
					:body="
						data.can_add
							? __('Add a file and the members of the group can open it.')
							: __('A leader can add a file to your group.')
					"
				>
					<Button
						v-if="data.can_add"
						variant="solid"
						size="lg"
						class="min-h-11"
						icon-left="lucide-plus"
						:label="__('Add a file')"
						@click="adding = true"
					/>
				</EmptyState>
			</section>
			<AddFileSheet
				v-if="data.can_add"
				v-model:open="adding"
				:groups="data.groups"
				@added="files.reload()"
			/>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { ref } from "vue";
import { useRoute } from "vue-router";

import { useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

import AddFileSheet from "./AddFileSheet.vue";
import type { GroupFiles } from "./types";

const route = useRoute();
const files = useRead<GroupFiles>("groups.get_group_files");
const { mark, isFresh } = useFreshInk();

// The old form's "New" path opens the sheet.
const adding = ref(
	String(route.params.rest ?? "")
		.split(",")
		.includes("new")
);

useLiveRefresh(["group-files", "groups"], async () => {
	const before = new Set(files.data?.items.map((file) => file.name));
	await files.reload();

	const added = files.data?.items.filter((file) => !before.has(file.name)) ?? [];
	added.forEach((file) => mark(file.name));
});
</script>
