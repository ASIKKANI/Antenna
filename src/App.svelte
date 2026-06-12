<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { CompanionWebSocket, type CompanionState } from "./lib/websocket";
  import { resizeWindow, startDragWindow, exitApp, isTauri } from "./lib/tauri";

  // ─── Reactive State ──────────────────────────────────────────
  let connectionStatus = "Initializing...";
  let companionState: CompanionState = {
    display_animation_frame: "idle_loop",
    active_bubble_dialogue: "",
    focus_points_balance: 100,
    current_level: 1,
    experience_progress_percentage: 0,
    evolution_stage: "drone",
    active_tasks_count: 0,
  };

  let displayedDialogue = "";
  let lastDismissedDialogue = "";
  let isTyping = false;
  let typewriterTimer: ReturnType<typeof setTimeout> | null = null;
  let showDashboard = false;
  let uiOpacity = 85; // 0 to 100
  let ws: CompanionWebSocket | null = null;

  // ─── Animation State Mapping ─────────────────────────────────
  $: animClass = getAnimationClass(companionState.display_animation_frame);
  $: evoClass = `evo-${companionState.evolution_stage}`;
  $: focusBarColor = getFocusBarColor(companionState.focus_points_balance);

  function getAnimationClass(frame: string): string {
    switch (frame) {
      case "focus_mode_active": return "anim-focused";
      case "nagging_mild": return "anim-warning";
      case "nagging_severe": return "anim-critical";
      case "celebrating": return "anim-celebrate";
      case "vision_capture": return "anim-focused";
      default: return "anim-idle";
    }
  }

  function getFocusBarColor(fp: number): string {
    if (fp > 70) return "var(--cp-accent)";
    if (fp > 40) return "var(--cp-accent-warm)";
    return "var(--cp-accent-danger)";
  }

  // ─── Typewriter Dialogue Effect ──────────────────────────────
  function typeDialogue(text: string) {
    if (typewriterTimer) clearTimeout(typewriterTimer);
    displayedDialogue = "";
    isTyping = true;
    let i = 0;

    function typeNext() {
      if (i < text.length) {
        displayedDialogue += text[i];
        i++;
        typewriterTimer = setTimeout(typeNext, 18 + Math.random() * 12);
      } else {
        isTyping = false;
      }
    }
    typeNext();
  }

  // ─── Interaction Logic ───────────────────────────────────────
  let isPointerDown = false;
  let startX = 0, startY = 0;

  function handlePointerDown(e: PointerEvent) {
    if (e.button !== 0) return; // Only left click
    isPointerDown = true;
    startX = e.screenX;
    startY = e.screenY;
  }

  function handlePointerMove(e: PointerEvent) {
    if (!isPointerDown) return;
    const dx = Math.abs(e.screenX - startX);
    const dy = Math.abs(e.screenY - startY);
    
    // If mouse moves more than 5 pixels, it's a drag! Hand it off to the OS.
    if (dx > 5 || dy > 5) {
      isPointerDown = false; // Reset so we don't spam IPC
      startDragWindow(); // OS takes over
    }
  }

  async function handlePointerUp(e: PointerEvent) {
    if (!isPointerDown || e.button !== 0) return;
    
    // If we get here, it means we clicked without dragging.
    isPointerDown = false;
    showDashboard = !showDashboard;
    if (showDashboard) {
      await resizeWindow(360, 600);
    } else {
      await resizeWindow(360, 250);
    }
  }

  async function closeDashboard() {
    showDashboard = false;
    await resizeWindow(360, 250);
  }

  // ─── Evolution Badge ─────────────────────────────────────────
  function getEvolutionEmoji(stage: string): string {
    switch (stage) {
      case "drone": return "🤖";
      case "scout": return "🛸";
      case "sentinel": return "⚡";
      case "guardian": return "🛡️";
      case "titan": return "👑";
      default: return "🤖";
    }
  }

  function getEvolutionLabel(stage: string): string {
    return stage.charAt(0).toUpperCase() + stage.slice(1);
  }

  // ─── Lifecycle ───────────────────────────────────────────────
  onMount(() => {
    ws = new CompanionWebSocket(
      (state) => {
        companionState = state;
        if (state.active_bubble_dialogue && 
            state.active_bubble_dialogue !== displayedDialogue && 
            state.active_bubble_dialogue !== lastDismissedDialogue) {
          typeDialogue(state.active_bubble_dialogue);
        } else if (!state.active_bubble_dialogue) {
          displayedDialogue = "";
          lastDismissedDialogue = "";
        }
      },
      (status) => {
        connectionStatus = status;
      }
    );
  });

  onDestroy(() => {
    ws?.destroy();
    if (typewriterTimer) clearTimeout(typewriterTimer);
  });
</script>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- MAIN LAYOUT                                                    -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<main class="w-screen h-screen flex flex-col items-center justify-start p-2 mt-[60px]"
      style="--ui-opacity: {uiOpacity / 100};">

  <!-- Sprite Container (Draggable) -->
  <div class="sprite-container">
       
    <!-- The actual Sprite (SVG inline) -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="pet-sprite {animClass}" on:pointerdown={handlePointerDown} on:pointermove={handlePointerMove} on:pointerup={handlePointerUp} style="opacity: var(--ui-opacity); cursor: grab; background: rgba(1,1,1,0.01); border-radius: 50%;">
      <svg width="128" height="128" viewBox="0 0 128 128" fill="none" xmlns="http://www.w3.org/2000/svg" style="pointer-events: none;">
        <circle cx="64" cy="64" r="50" fill="#1e293b" stroke="#334155" stroke-width="4"/>
        <circle cx="64" cy="64" r="35" fill="#0f172a"/>
        <!-- Visor -->
        <rect x="40" y="55" width="48" height="14" rx="7" fill="#38bdf8" />
        <rect x="45" y="58" width="38" height="8" rx="4" fill="#e0f2fe" />
        <!-- Details -->
        <circle cx="64" cy="35" r="4" fill="#ef4444"/>
      </svg>
    </div>
         
    <!-- Dialogue Bubble (Only shows if typing or critical, or dashboard closed) -->
    {#if displayedDialogue && (!showDashboard || companionState.display_animation_frame === 'nagging_severe')}
      <div class="dialogue-float">
        <div class="dialogue-bubble">
          <span class="dialogue-text">{displayedDialogue}</span>
          {#if isTyping}
            <span class="typing-cursor">▌</span>
          {/if}
          <!-- Close button to dismiss dialogue bubble -->
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="bubble-close-btn" on:click={() => { lastDismissedDialogue = companionState.active_bubble_dialogue; displayedDialogue = ""; }} title="Dismiss">✕</div>
        </div>
      </div>
    {/if}
  </div>

  <!-- Dashboard Panel (Pop-up) -->
  {#if showDashboard}
    <div class="dashboard-panel">
      
      <!-- ─── Header Bar ───────────────────────────────────────── -->
      <div class="header-bar">
        <div class="flex items-center gap-2">
          <span class="status-dot" class:connected={connectionStatus === 'Connected'}></span>
          <span class="header-title">ChronosPet Core</span>
        </div>
        <div class="header-meta">
          <span class="evo-badge {evoClass}">
            {getEvolutionEmoji(companionState.evolution_stage)}
            {getEvolutionLabel(companionState.evolution_stage)}
          </span>
          <!-- Close Button -->
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="close-btn" on:click={exitApp} title="Exit Pet">✕</div>
        </div>
      </div>

      <!-- ─── Stats Section ────────────────────────────────────── -->
      <div class="stats-section">
        <div class="stat-row">
          <div class="stat-label">
            <span class="stat-icon">◈</span>
            <span>FOCUS</span>
          </div>
          <span class="stat-value" style="color: {focusBarColor};">{companionState.focus_points_balance} FP</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill"
               style="width: {companionState.focus_points_balance}%; background: {focusBarColor};">
          </div>
        </div>

        <div class="stat-row" style="margin-top: 10px;">
          <div class="stat-label">
            <span class="stat-icon">✦</span>
            <span>LEVEL {companionState.current_level}</span>
          </div>
          <span class="stat-value" style="color: var(--cp-accent-xp);">
            {Math.round(companionState.experience_progress_percentage)}%
          </span>
        </div>
        <div class="progress-track">
          <div class="progress-fill xp-bar-fill"
               style="width: {companionState.experience_progress_percentage}%;">
          </div>
        </div>
      </div>

      <!-- ─── Active Tasks Count ───────────────────────────────── -->
      <div class="tasks-bar">
        <div class="tasks-bar-inner">
          <span class="tasks-label">
            {#if companionState.active_tasks_count > 0}
              🎯 {companionState.active_tasks_count} active task{companionState.active_tasks_count !== 1 ? 's' : ''}
            {:else}
              💤 No active tasks
            {/if}
          </span>
          <span class="state-label">{companionState.display_animation_frame}</span>
        </div>
      </div>

      <!-- ─── Controls & Footer ───────────────────────────────── -->
      <div class="footer-bar">
        <div class="controls">
          <label for="opacity">UI Opacity:</label>
          <input type="range" id="opacity" min="20" max="100" bind:value={uiOpacity} class="opacity-slider" />
        </div>
        <span class="connection-status">{connectionStatus}</span>
      </div>
    </div>
  {/if}
</main>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- SCOPED STYLES                                                  -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<style>
  /* ─── Sprite ───────────────────────────────────────────────── */
  .sprite-container {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: grab;
    z-index: 10;
  }
  .sprite-container:active {
    cursor: grabbing;
  }

  .pet-sprite {
    width: 128px;
    height: 128px;
    object-fit: contain;
    filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5));
    transition: filter 0.3s ease, transform 0.3s ease;
  }
  .pet-sprite:hover {
    filter: drop-shadow(0 0 15px var(--cp-accent-glow));
    transform: scale(1.05);
  }

  /* ─── Sprite Animations ────────────────────────────────────── */
  .anim-idle {
    animation: avatar-idle 3s ease-in-out infinite;
  }
  .anim-focused {
    animation: avatar-focused 2.5s ease-in-out infinite;
    filter: drop-shadow(0 0 15px rgba(99, 102, 241, 0.6)) hue-rotate(-20deg) brightness(1.2);
  }
  .anim-warning {
    animation: avatar-warning 0.8s ease-in-out infinite;
    filter: drop-shadow(0 0 20px rgba(245, 158, 11, 0.8)) sepia(1) hue-rotate(-30deg) saturate(3);
  }
  .anim-critical {
    animation: avatar-critical 0.4s ease-in-out infinite;
    filter: drop-shadow(0 0 25px rgba(239, 68, 68, 0.9)) sepia(1) hue-rotate(-50deg) saturate(5) brightness(0.8);
  }
  .anim-celebrate {
    animation: avatar-celebrate 1.5s ease-in-out;
    filter: drop-shadow(0 0 20px rgba(16, 185, 129, 0.7)) hue-rotate(90deg) brightness(1.3);
  }

  /* ─── Floating Dialogue ────────────────────────────────────── */
  .dialogue-float {
    position: absolute;
    top: -50px;
    left: 50%;
    transform: translateX(-50%);
    width: max-content;
    max-width: 250px;
    z-index: 20;
    pointer-events: none;
  }

  .dialogue-bubble {
    position: relative;
    background: rgba(15, 18, 40, var(--ui-opacity));
    backdrop-filter: blur(12px);
    border: 1px solid var(--cp-border);
    border-radius: var(--cp-radius-sm);
    padding: 10px 20px 10px 14px; /* Extra right padding for close button */
    font-size: 12px;
    line-height: 1.5;
    color: var(--cp-text-primary);
    box-shadow: var(--cp-shadow);
    pointer-events: auto; /* Enable mouse events for close button click */
  }

  .bubble-close-btn {
    position: absolute;
    top: 2px;
    right: 5px;
    font-size: 9px;
    color: var(--cp-text-secondary);
    cursor: pointer;
    line-height: 1;
    padding: 2px;
    transition: color 0.2s;
  }
  .bubble-close-btn:hover {
    color: var(--cp-accent-danger);
  }
  .dialogue-bubble::before {
    content: '';
    position: absolute;
    bottom: -6px;
    left: 50%;
    transform: translateX(-50%) rotate(45deg);
    width: 10px;
    height: 10px;
    background: inherit;
    border-right: 1px solid var(--cp-border);
    border-bottom: 1px solid var(--cp-border);
  }

  /* ─── Dashboard Panel ──────────────────────────────────────── */
  .dashboard-panel {
    margin-top: 16px;
    width: 320px;
    background: rgba(10, 12, 28, var(--ui-opacity));
    backdrop-filter: blur(24px) saturate(1.4);
    -webkit-backdrop-filter: blur(24px) saturate(1.4);
    border: 1px solid var(--cp-border);
    border-radius: var(--cp-radius);
    box-shadow: var(--cp-shadow), var(--cp-shadow-glow);
    overflow: hidden;
    animation: slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes slide-up {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* ─── Header ───────────────────────────────────────────────── */
  .header-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--cp-border);
  }
  .header-title {
    font-family: var(--cp-font-mono);
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 1px;
    color: var(--cp-text-primary);
  }
  .header-meta {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .evo-badge {
    font-size: 10px;
    font-weight: 600;
    font-family: var(--cp-font-mono);
    padding: 3px 8px;
    border-radius: 100px;
    background: rgba(99, 102, 241, 0.15);
    color: var(--evo-color, var(--cp-text-accent));
    border: 1px solid rgba(99, 102, 241, 0.2);
    letter-spacing: 0.5px;
  }
  .close-btn {
    font-size: 14px;
    color: var(--cp-text-secondary);
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    transition: all 0.2s;
    margin-left: 4px;
  }
  .close-btn:hover {
    color: var(--cp-accent-danger);
    background: rgba(239, 68, 68, 0.1);
  }

  /* ─── Status Dot ───────────────────────────────────────────── */
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--cp-accent-danger);
    animation: status-pulse 2s ease-in-out infinite;
  }
  .status-dot.connected {
    background: var(--cp-accent-success);
  }

  /* ─── Stats ────────────────────────────────────────────────── */
  .stats-section {
    padding: 12px 16px;
    border-top: 1px solid var(--cp-border);
  }
  .stat-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .stat-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: var(--cp-font-mono);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.2px;
    color: var(--cp-text-secondary);
    text-transform: uppercase;
  }
  .stat-icon {
    font-size: 11px;
    opacity: 0.7;
  }
  .stat-value {
    font-family: var(--cp-font-mono);
    font-size: 11px;
    font-weight: 600;
  }

  .progress-track {
    width: 100%;
    height: 5px;
    background: var(--cp-bg-input);
    border-radius: 100px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.03);
  }
  .progress-fill {
    height: 100%;
    border-radius: 100px;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1),
                background 0.5s ease;
  }

  /* ─── Tasks Bar ────────────────────────────────────────────── */
  .tasks-bar {
    padding: 10px 16px;
    border-top: 1px solid var(--cp-border);
  }
  .tasks-bar-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .tasks-label {
    font-size: 11px;
    color: var(--cp-text-secondary);
  }
  .state-label {
    font-family: var(--cp-font-mono);
    font-size: 9px;
    color: var(--cp-text-muted);
    padding: 2px 6px;
    background: var(--cp-bg-input);
    border-radius: var(--cp-radius-xs);
    border: 1px solid var(--cp-border);
  }

  /* ─── Footer & Controls ────────────────────────────────────── */
  .footer-bar {
    padding: 8px 16px;
    border-top: 1px solid var(--cp-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .controls {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
    color: var(--cp-text-muted);
    font-family: var(--cp-font-mono);
  }
  .opacity-slider {
    width: 60px;
    height: 4px;
    -webkit-appearance: none;
    background: var(--cp-bg-input);
    border-radius: 2px;
    outline: none;
  }
  .opacity-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--cp-accent);
    cursor: pointer;
  }
  .connection-status {
    font-family: var(--cp-font-mono);
    font-size: 9px;
    color: var(--cp-text-muted);
    letter-spacing: 0.5px;
  }
  
  .typing-cursor {
    color: var(--cp-accent-glow);
    animation: typewriter-blink 0.8s step-end infinite;
    font-size: 12px;
    margin-left: 1px;
  }
</style>
