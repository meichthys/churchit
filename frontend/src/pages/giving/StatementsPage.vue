<template>
	<PageHead
		:crumbs="[{ label: __('Giving') }, { label: __('Giving Statements') }]"
	/>
	<PageBody>
		<Masthead
			:title="__('Giving Statements')"
			:label="boot.church?.title"
			:dateline="
				__('Your giving, year by year, to keep for your records')
			"
		/>
		<LoadState :resource="statements" v-slot="{ data }">
			<section v-if="data.items.length" class="mt-8">
				<template v-for="group in years(data.items)" :key="group.year">
					<SectionHead :title="group.year" />
					<ul
						class="mb-8 divide-y divide-outline-gray-1 border-t border-outline-gray-1"
					>
						<li
							v-for="statement in group.items"
							:key="statement.name"
						>
							<IndexRow
								:title="statement.title"
								:facts="[
									statement.period_display,
									statement.total_display,
								]"
							>
								<template #suffix>
									<Button
										class="min-h-11"
										variant="outline"
										size="lg"
										icon-left="lucide-printer"
										:label="__('Open to print')"
										@click="open(statement.name)"
									/>
								</template>
							</IndexRow>
						</li>
					</ul>
				</template>
			</section>
			<EmptyState
				v-else
				class="mt-8"
				:title="__('No statements yet')"
				:body="
					__(
						'The church issues your giving statement after the year ends. It will be listed here.',
					)
				"
			/>
		</LoadState>
	</PageBody>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";

import { useRead } from "@/api";
import { boot } from "@/boot";
import EmptyState from "@/components/EmptyState.vue";
import IndexRow from "@/components/IndexRow.vue";
import LoadState from "@/components/LoadState.vue";
import Masthead from "@/components/Masthead.vue";
import PageBody from "@/components/PageBody.vue";
import PageHead from "@/components/PageHead.vue";
import SectionHead from "@/components/SectionHead.vue";
import { __ } from "@/translate";

import type { Statement } from "./types";

const statements = useRead<{ items: Statement[] }>("giving.get_statements");

function years(items: Statement[]) {
	const groups: { year: string; items: Statement[] }[] = [];
	for (const statement of items) {
		const year = statement.to_date.slice(0, 4);
		const group = groups.find((row) => row.year === year);
		if (group) group.items.push(statement);
		else groups.push({ year, items: [statement] });
	}
	return groups;
}

/** The printable statement is a website page, so it loads whole. */
function open(name: string) {
	window.location.href = `/statements?name=${encodeURIComponent(name)}`;
}
</script>
