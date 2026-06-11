/**
 * ChronosPet — Tauri IPC Wrappers
 * ================================
 * Typed wrappers for Rust backend commands exposed via Tauri v2.
 */

let invoke: ((cmd: string, args?: Record<string, unknown>) => Promise<unknown>) | null = null;

// Dynamic import — only works inside Tauri, gracefully fails in browser dev
async function loadInvoke() {
  if (invoke) return invoke;
  try {
    const api = await import("@tauri-apps/api/core");
    invoke = api.invoke;
    return invoke;
  } catch {
    console.warn("[Tauri] Not running inside Tauri — IPC commands will be no-ops.");
    return null;
  }
}

/**
 * Toggle click-through mode on the main window.
 * - `ignore: true`  → clicks pass through to underlying windows
 * - `ignore: false` → window captures mouse events (for avatar interaction)
 */
export async function resizeWindow(width: number, height: number): Promise<void> {
  const inv = await loadInvoke();
  if (!inv) return;
  try {
    await inv("resize_window", { width, height });
  } catch (error) {
    console.error("Failed to resize window:", error);
  }
}

/**
 * Check if we're running inside a Tauri window.
 */
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function startDragWindow(): Promise<void> {
  const inv = await loadInvoke();
  if (!inv) return;
  try {
    await inv("start_drag");
  } catch (error) {
    console.error("Failed to start drag:", error);
  }
}

export async function startDrag(): Promise<void> {
  if (!isTauri()) return;
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    await getCurrentWindow().startDragging();
  } catch (err) {
    console.error("Failed to start drag:", err);
  }
}

export async function exitApp(): Promise<void> {
  const inv = await loadInvoke();
  if (!inv) return;
  try {
    await inv("exit_app");
  } catch (error) {
    console.error("Failed to exit app:", error);
  }
}
