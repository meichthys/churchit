import { io, type Socket } from "socket.io-client";
import { onBeforeUnmount, onMounted } from "vue";

import { boot } from "./boot";

/** The event churchit.portal.realtime.notify sends to the signed-in user's room. */
const EVENT = "churchit_portal";
/** A tab that comes back into view reads again, at most this often. */
const REFRESH_ON_VIEW_MS = 30_000;

export interface LiveHint {
	topic: string;
	name: string | null;
}

let socket: Socket | null = null;
const hintHandlers = new Set<(hint: LiveHint) => void>();
const reconnectHandlers = new Set<() => void>();

/** Behind the production proxy socket.io shares the page's origin; a dev server gives it a port of its own. */
function socketUrl(): string {
	const url = new URL(window.location.origin);
	if (boot.socketio_port && url.port) url.port = String(boot.socketio_port);
	return `${url.origin}/${boot.site_name}`;
}

/** WebSocket first (a dev server's separate port allows no cross-origin polling), polling when a proxy
 * refuses the upgrade. After a few failed tries the app stops and reads again when a tab comes back. */
function connect(): void {
	if (socket || !boot.realtime) return;
	socket = io(socketUrl(), {
		withCredentials: true,
		transports: ["websocket", "polling"],
		tryAllTransports: true,
		reconnectionAttempts: 5,
	});
	socket.on(EVENT, (hint: LiveHint) => hintHandlers.forEach((handler) => handler(hint)));
	socket.io.on("reconnect", () => reconnectHandlers.forEach((handler) => handler()));
}

/**
 * Call *refresh* when the server says one of *topics* changed, when the socket reconnects (hints sent
 * while it was away are lost) and when the tab comes back into view. A hint carries no data: refresh
 * reads it again through the page's own GET.
 */
export function useLiveRefresh(topics: string[], refresh: (hint: LiveHint | null) => void): void {
	let lastRefresh = Date.now();
	const run = (hint: LiveHint | null) => {
		lastRefresh = Date.now();
		refresh(hint);
	};
	const onHint = (hint: LiveHint) => topics.includes(hint.topic) && run(hint);
	const onReconnect = () => run(null);
	const onVisible = () => {
		if (document.visibilityState !== "visible") return;
		if (socket && !socket.connected) socket.connect();
		if (Date.now() - lastRefresh > REFRESH_ON_VIEW_MS) run(null);
	};

	onMounted(() => {
		connect();
		hintHandlers.add(onHint);
		reconnectHandlers.add(onReconnect);
		document.addEventListener("visibilitychange", onVisible);
	});
	onBeforeUnmount(() => {
		hintHandlers.delete(onHint);
		reconnectHandlers.delete(onReconnect);
		document.removeEventListener("visibilitychange", onVisible);
	});
}
