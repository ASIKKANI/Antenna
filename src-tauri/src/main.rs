// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager, Emitter};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

/// IPC Command: Resize the main window dynamically.
#[tauri::command]
fn resize_window(window: tauri::Window, width: f64, height: f64) -> Result<(), String> {
    window
        .set_size(tauri::Size::Logical(tauri::LogicalSize { width, height }))
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn start_drag(window: tauri::Window) -> Result<(), String> {
    window.start_dragging().map_err(|e| e.to_string())
}

#[tauri::command]
fn exit_app() {
    std::process::exit(0);
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            // Get the main window handle
            let window = app
                .get_webview_window("main")
                .expect("Failed to get 'main' window — check tauri.conf.json label");

            // We no longer ignore cursor events globally.
            // The window size physically resizes instead.

            // Register Ctrl+Shift+C hotkey for vision capture (PRD Req-E.3)
            #[cfg(desktop)]
            {
                let ctrl_shift_c =
                    Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::KeyC);

                let window_clone = window.clone();
                app.global_shortcut()
                    .on_shortcut(ctrl_shift_c, move |_app_handle, _shortcut, event| {
                        if event.state() == ShortcutState::Pressed {
                            println!("[HOTKEY] Vision Capture triggered (Ctrl+Shift+C)");
                            // Disable click-through so user can interact with the capture UI
                            let _ = window_clone.set_ignore_cursor_events(false);

                            // Emit event to frontend to enter vision capture mode
                            let _ = window_clone.emit("vision-capture", "activate");
                        }
                    })?;
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![resize_window, start_drag, exit_app])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
