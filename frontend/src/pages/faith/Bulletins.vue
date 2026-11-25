<template>
	<PageHead :crumbs="[{ label: __('Bulletins') }]" />

	<PageBody>
		<Masthead
			:title="__('Bulletins')"
			:label="boot.church?.title"
			:dateline="__('The weekly order of service, to read or print')"
		/>

		<LoadState :resource="bulletins" v-slot="{ data }">
			<section class="mt-8" aria-labelledby="bulletin-list">
				<SectionHead id="bulletin-list" :title="__('Newest first')" />
				<ul
					v-if="data.items.length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="item in data.items" :key="item.name">
						<IndexRow
							:title="item.title"
							:facts="[item.date_display]"
						>
							<template #prefix
								><DateStack v-if="item.date" :date="item.date"
							/></template>
							<div class="mt-3 flex flex-wrap gap-2">
								<a
									:href="item.digital_url"
									:class="[
										linkClass,
										'bg-surface-gray-7 text-ink-white hover:bg-surface-gray-6',
									]"
									>{{ __("Read") }}</a
								>
								<a
									:href="item.pdf_url"
									:class="[
										linkClass,
										'border border-outline-gray-2 text-ink-gray-8 hover:bg-surface-gray-2',
									]"
								>
									<span
										class="lucide-file-down size-4"
										aria-hidden="true"
									/>{{ __("PDF") }}
								</a>
							</div>
						</IndexRow>
					</li>
				</ul>
				<EmptyState
					v-else
					:title="__('No bulletins yet')"
					:body="
						__(
							'The church shares a bulletin here after each service.',
						)
					"
				/>
			</section>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { boot } from "@/boot";
import DateStack from "@/components/DateStack.vue";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { useRead } from "@/api";
import { useLiveRefresh } from "@/realtime";

interface BulletinList {
	items: {
		name: string;
		title: string;
		date: string | null;
		date_display: string | null;
		digital_url: string;
		pdf_url: string;
	}[];
}

const bulletins = useRead<BulletinList>("faith.get_bulletins");
useLiveRefresh([], () => bulletins.reload());

const linkClass =
	"inline-flex min-h-11 items-center justify-center gap-2 rounded px-4 text-base font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3";
</script>
