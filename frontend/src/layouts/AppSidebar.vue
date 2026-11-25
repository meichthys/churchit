<template>
	<Sidebar
		:collapsible="false"
		width="16rem"
		:aria-label="__('Member portal')"
		class="border-e border-outline-gray-1"
	>
		<SidebarHeader
			:title="boot.church?.title || __('Member portal')"
			:subtitle="boot.household || boot.user.full_name"
			:logo="boot.church?.logo || undefined"
		/>

		<div class="min-h-0 flex-1 overflow-y-auto px-2 pb-4 pt-2">
			<NavItem :item="thisWeek" />
			<NavItem v-if="checkIn" :item="checkIn" />

			<template v-for="section in sections" :key="section.label">
				<SidebarLabel class="mt-5">
					<span class="t-label text-ink-gray-6">{{
						section.label
					}}</span>
				</SidebarLabel>
				<NavItem
					v-for="item in section.items"
					:key="item.key"
					:item="item"
				/>
			</template>

			<template v-if="elsewhere.length">
				<SidebarLabel class="mt-5">
					<span class="t-label text-ink-gray-6">{{
						__("Elsewhere")
					}}</span>
				</SidebarLabel>
				<NavItem
					v-for="item in elsewhere"
					:key="item.key"
					:item="item"
				/>
			</template>
		</div>

		<div class="border-t border-outline-gray-1 p-2">
			<SidebarItem :label="boot.user.full_name" route="/personal-details">
				<template #prefix>
					<Avatar
						:label="boot.user.full_name"
						:image="boot.user.image || undefined"
						size="sm"
					/>
				</template>
				<span class="truncate text-base">{{
					boot.user.full_name
				}}</span>
				<template #suffix>
					<button
						type="button"
						class="me-1 flex size-7 items-center justify-center rounded-4 text-ink-gray-6 hover:bg-surface-gray-3 hover:text-ink-gray-9"
						:aria-label="__('Sign out')"
						:title="__('Sign out')"
						@click="signOut"
					>
						<span
							class="lucide-log-out size-4 rtl:-scale-x-100"
							aria-hidden="true"
						/>
					</button>
				</template>
			</SidebarItem>
		</div>
	</Sidebar>
</template>

<script setup lang="ts">
import {
	Avatar,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarLabel,
} from "frappe-ui";

import { signOut } from "@/api";
import { boot } from "@/boot";
import NavItem from "@/layouts/NavItem.vue";
import { checkIn, elsewhere, sections, thisWeek } from "@/navigation";
</script>
