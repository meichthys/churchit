<template>
	<BottomSheet v-model:open="open" :title="__('More')">
		<nav class="px-5 pb-8" :aria-label="__('More')">
			<section
				v-for="section in moreSections"
				:key="section.label"
				class="mt-5 first:mt-1"
			>
				<h2 class="t-label px-1 text-ink-gray-6">
					{{ section.label }}
				</h2>
				<ul class="mt-1">
					<li v-for="item in section.items" :key="item.key">
						<a
							class="flex min-h-12 items-center gap-3 rounded-4 px-1 text-lg text-ink-gray-8 hover:bg-surface-gray-2"
							:href="
								item.route
									? router.resolve(item.route).href
									: item.href
							"
							:target="item.target"
							@click="go($event, item)"
						>
							<span
								class="size-5 shrink-0 text-ink-gray-6"
								:class="item.icon"
								aria-hidden="true"
							/>
							<span class="min-w-0 flex-1">{{ item.label }}</span>
							<span
								v-if="item.href"
								class="lucide-arrow-up-right size-4 shrink-0 text-ink-gray-5 rtl:-scale-x-100"
								aria-hidden="true"
							/>
						</a>
					</li>
				</ul>
			</section>

			<div
				class="mt-6 flex items-center gap-3 border-t border-outline-gray-1 pt-4"
			>
				<Avatar
					:label="boot.user.full_name"
					:image="boot.user.image || undefined"
					size="lg"
				/>
				<div class="min-w-0 flex-1">
					<p class="text-lg font-medium text-ink-gray-9">
						{{ boot.user.full_name }}
					</p>
					<p class="text-md text-ink-gray-6">
						{{ boot.church?.title }}
					</p>
				</div>
			</div>
			<Button
				variant="subtle"
				size="lg"
				icon-left="lucide-log-out"
				:label="__('Sign out')"
				class="mt-4 min-h-11 w-full"
				@click="signOut"
			/>
		</nav>
	</BottomSheet>
</template>

<script setup lang="ts">
import { Avatar, BottomSheet, Button } from "frappe-ui";
import { useRouter } from "vue-router";

import { signOut } from "@/api";
import { boot } from "@/boot";
import { moreSections, type MenuItem } from "@/navigation";

const open = defineModel<boolean>("open", { default: false });
const router = useRouter();

function go(event: MouseEvent, item: MenuItem) {
	open.value = false;
	if (!item.route || event.metaKey || event.ctrlKey) return;
	event.preventDefault();
	router.push(item.route);
}
</script>
