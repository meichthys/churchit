import { FrappeResponseError, toast, useCall } from "frappe-ui";
import type { BasicParams, UseCallOptions } from "frappe-ui";

import { boot } from "./boot";
import { __ } from "./translate";

type CallOptions<T, P extends BasicParams> = Omit<UseCallOptions<T, P>, "url" | "method">;

/** The v2 URL of a portal endpoint, from its path under churchit.portal, such as "household.get_household". */
export function portalUrl(path: string): string {
	return `/api/v2/method/churchit.portal.${path}`;
}

/** A GET read of a portal endpoint. It runs at once; the page shows `error` itself. */
export function useRead<T, P extends BasicParams = undefined>(path: string, options: CallOptions<T, P> = {}) {
	return useCall<T, P>({ url: portalUrl(path), method: "GET", onError: handleSessionError, ...options });
}

/** A POST change through a portal endpoint. Nothing is sent until submit(); a failure is shown as a toast,
 * and submit() still rejects, so `await action.submit(...).catch(() => {})` when nothing else should run. */
export function useAction<T, P extends BasicParams = undefined>(path: string, options: CallOptions<T, P> = {}) {
	return useCall<T, P>({ url: portalUrl(path), method: "POST", immediate: false, onError: reportError, ...options });
}

/** A POST to a whitelisted method by its dotted path, for the few changes the app makes through an existing
 * tested endpoint, such as churchit.church_communications.preferences.set_preference. */
export function useFrappeAction<T, P extends BasicParams = undefined>(method: string, options: CallOptions<T, P> = {}) {
	return useCall<T, P>({ url: `/api/v2/method/${method}`, method: "POST", immediate: false, onError: reportError, ...options });
}

/** The message of an error, without the "Type: " prefix of Frappe's v2 errors or any markup. */
export function errorText(error: unknown): string {
	if (error instanceof FrappeResponseError) {
		const prefix = `${error.type}: `;
		const message = error.message.startsWith(prefix) ? error.message.slice(prefix.length) : error.message;
		return stripTags(message) || __("Something went wrong. Please try again.");
	}
	if (error instanceof Error && error.message) return stripTags(error.message);
	return __("Something went wrong. Please try again.");
}

/** Show *error* as a toast, unless the session ended (then the page reloads into the sign-in page). */
export function reportError(error: unknown): void {
	if (!handleSessionError(error)) toast.error(errorText(error));
}

/** Reload when the session ended, by expiry or a sign-out in another tab: the page then asks for a login. */
export function handleSessionError(error: unknown): boolean {
	if (!(error instanceof FrappeResponseError)) return false;
	const signedOut =
		error.type === "SessionExpired" ||
		(error.type === "PermissionError" && getCookie("user_id") !== boot.user.name);
	if (signedOut) window.location.reload();
	return signedOut;
}

function getCookie(name: string): string | null {
	const match = document.cookie.split("; ").find((row) => row.startsWith(name + "="));
	return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

function stripTags(html: string): string {
	return new DOMParser().parseFromString(html, "text/html").body.textContent?.trim() || "";
}

/** Sign out through Frappe's own endpoint, then land on the sign-in page. */
export async function signOut(): Promise<void> {
	await fetch("/api/method/logout", {
		method: "POST",
		headers: { "X-Frappe-CSRF-Token": window.csrf_token || "", Accept: "application/json" },
	}).catch(() => {});
	window.location.href = "/login";
}

