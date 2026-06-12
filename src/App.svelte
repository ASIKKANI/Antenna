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
    selected_pet_id: "default_drone",
  };

  let displayedDialogue = "";
  let lastDismissedDialogue = "";
  let isTyping = false;
  let typewriterTimer: ReturnType<typeof setTimeout> | null = null;
  let showDashboard = false;
  let uiOpacity = 85; // 0 to 100
  let ws: CompanionWebSocket | null = null;

  // ─── Companion Pet State ─────────────────────────────────────
  let pets: any[] = [];
  let selectedPetId = "default_drone";
  let petCanvas: HTMLCanvasElement | null = null;
  let rafId: number | null = null;

  interface Particle {
    x: number;
    y: number;
    vx: number;
    vy: number;
    color: string;
    life: number;
    decay: number;
    size: number;
    type: string;
  }

  let particles: Particle[] = [];
  let particleOverride: "heart" | "food" | null = null;
  let particleTimer: ReturnType<typeof setTimeout> | null = null;

  async function interact(action: "pet" | "feed") {
    // Set optimistically for instant feedback
    particleOverride = action === "pet" ? "heart" : "food";
    if (particleTimer) clearTimeout(particleTimer);
    particleTimer = setTimeout(() => {
      particleOverride = null;
      particleTimer = null;
    }, 3500);

    try {
      const response = await fetch("http://localhost:8000/api/v1/companion/interact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action })
      });
      if (!response.ok) {
        // Revert if API failed
        particleOverride = null;
        if (particleTimer) {
          clearTimeout(particleTimer);
          particleTimer = null;
        }
      } else {
        await fetchPets();
      }
    } catch (err) {
      console.error(`Failed to trigger ${action}:`, err);
      particleOverride = null;
      if (particleTimer) {
        clearTimeout(particleTimer);
        particleTimer = null;
      }
    }
  }

  async function fetchPets() {
    try {
      const response = await fetch("http://localhost:8000/api/v1/companion/pets");
      if (response.ok) {
        const data = await response.json();
        pets = data.pets;
        selectedPetId = data.selected_pet_id || "default_drone";
      }
    } catch (err) {
      console.error("Failed to fetch pets:", err);
    }
  }

  function spawnParticle(state: string) {
    if (Math.random() > 0.4) return;
    
    let color = "#38bdf8";
    let vx = (Math.random() - 0.5) * 0.5;
    let vy = -Math.random() * 0.8 - 0.2;
    let size = Math.random() > 0.5 ? 2 : 1;
    let decay = Math.random() * 0.02 + 0.01;
    let type = "normal";
    
    if (particleOverride === "heart") {
      type = "heart";
      color = "#f43f5e";
      vx = (Math.random() - 0.5) * 0.8;
      vy = -Math.random() * 0.8 - 0.4;
      decay = Math.random() * 0.015 + 0.01;
    } else if (particleOverride === "food") {
      type = "food";
      color = "#d97706";
      vx = (Math.random() - 0.5) * 0.6;
      vy = Math.random() * 0.8 + 0.4;
      decay = Math.random() * 0.02 + 0.015;
    } else {
      if (state === "focus_mode_active") {
        color = Math.random() > 0.5 ? "#8b5cf6" : "#38bdf8";
        vy = -Math.random() * 0.6 - 0.2;
      } else if (state === "nagging_mild" || state === "nagging_severe") {
        color = Math.random() > 0.5 ? "#ef4444" : "#f59e0b";
        vx = (Math.random() - 0.5) * 0.8;
        vy = -Math.random() * 0.5 - 0.3;
      } else if (state === "celebrating") {
        color = Math.random() > 0.5 ? "#fbbf24" : "#34d399";
        vx = (Math.random() - 0.5) * 1.5;
        vy = -Math.random() * 1.2 - 0.4;
        size = Math.random() > 0.5 ? 3 : 2;
      } else {
        if (Math.random() > 0.15) return;
        color = "rgba(255, 255, 255, 0.3)";
        vy = -Math.random() * 0.3 - 0.1;
      }
    }
    
    let x = 32 + Math.random() * 64;
    let y = type === "food" ? 10 + Math.random() * 10 : 80 + Math.random() * 20;

    particles.push({
      x,
      y,
      vx,
      vy,
      color,
      life: 1.0,
      decay,
      size,
      type
    });
  }

  function renderLoop() {
    if (!petCanvas) {
      rafId = requestAnimationFrame(renderLoop);
      return;
    }
    
    const ctx = petCanvas.getContext("2d");
    if (!ctx) {
      rafId = requestAnimationFrame(renderLoop);
      return;
    }
    
    ctx.clearRect(0, 0, petCanvas.width, petCanvas.height);
    
    const pet = pets.find(p => p.id === selectedPetId);
    if (pet) {
      let stateName = companionState.display_animation_frame || "idle_loop";
      let stateData = pet.states[stateName];
      if (!stateData || !stateData.frames || stateData.frames.length === 0) {
        stateName = "idle_loop";
        stateData = pet.states[stateName];
      }
      if (!stateData || !stateData.frames || stateData.frames.length === 0) {
        const keys = Object.keys(pet.states);
        if (keys.length > 0) {
          stateName = keys[0];
          stateData = pet.states[stateName];
        }
      }
      
      if (stateData && stateData.frames && stateData.frames.length > 0) {
        const speedMs = stateData.speed_ms || 400;
        const totalFrames = stateData.frames.length;
        const now = Date.now();
        const frameIdx = Math.floor(now / speedMs) % totalFrames;
        const frame = stateData.frames[frameIdx];
        
        if (frame) {
          const resolution = Math.sqrt(frame.length);
          const cellWidth = petCanvas.width / resolution;
          const cellHeight = petCanvas.height / resolution;
          
          for (let i = 0; i < frame.length; i++) {
            const color = frame[i];
            if (color) {
              const r = Math.floor(i / resolution);
              const c = i % resolution;
              ctx.fillStyle = color;
              ctx.fillRect(c * cellWidth, r * cellHeight, cellWidth, cellHeight);
            }
          }
        }
      }
    }
    
    const stateName = companionState.display_animation_frame || "idle_loop";
    spawnParticle(stateName);
    
    particles = particles.filter(p => {
      p.x += p.vx;
      p.y += p.vy;
      p.life -= p.decay;
      
      if (p.life > 0) {
        ctx.globalAlpha = p.life;
        if (p.type === "heart") {
          ctx.fillStyle = "#f43f5e"; // rose pink
          const px = Math.floor(p.x);
          const py = Math.floor(p.y);
          ctx.fillRect(px, py, 1, 1);
          ctx.fillRect(px + 2, py, 1, 1);
          ctx.fillRect(px, py + 1, 3, 1);
          ctx.fillRect(px + 1, py + 2, 1, 1);
        } else if (p.type === "food") {
          ctx.fillStyle = "#d97706"; // amber brown
          const px = Math.floor(p.x);
          const py = Math.floor(p.y);
          ctx.fillRect(px, py, 2, 2);
          ctx.fillStyle = "#78350f"; // dark chocolate chip
          ctx.fillRect(px, py, 1, 1);
        } else {
          ctx.fillStyle = p.color;
          ctx.fillRect(Math.floor(p.x), Math.floor(p.y), p.size, p.size);
        }
        ctx.globalAlpha = 1.0;
        return true;
      }
      return false;
    });
    
    rafId = requestAnimationFrame(renderLoop);
  }

  $: if (companionState.selected_pet_id && companionState.selected_pet_id !== selectedPetId) {
    selectedPetId = companionState.selected_pet_id;
    fetchPets();
  }

  $: {
    if (petCanvas && !rafId) {
      rafId = requestAnimationFrame(renderLoop);
    }
  }

  // ─── Task Management State ─────────────────────────────────────
  let activeTab: "core" | "tasks" | "interact" = "core";
  let tasks: any[] = [];
  let newTaskTitle = "";
  let newTaskPriority = "medium";
  let newTaskDeadlineHours = 1;

  async function fetchTasks() {
    try {
      const response = await fetch("http://localhost:8000/api/v1/tasks");
      if (response.ok) {
        const data = await response.json();
        // Sort: active/pending first, then failed, then completed
        const statusOrder: Record<string, number> = { active: 1, pending: 2, failed: 3, completed: 4 };
        tasks = data.tasks.sort((a: any, b: any) => {
          return (statusOrder[a.status_state] || 5) - (statusOrder[b.status_state] || 5);
        });
      }
    } catch (err) {
      console.error("Failed to fetch tasks:", err);
    }
  }

  async function addTask() {
    if (!newTaskTitle.trim()) return;
    try {
      const deadlineEpoch = Math.floor(Date.now() / 1000) + (newTaskDeadlineHours * 3600);
      const response = await fetch("http://localhost:8000/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clean_title: newTaskTitle.trim(),
          deadline_epoch: deadlineEpoch,
          priority_level: newTaskPriority
        })
      });
      if (response.ok) {
        newTaskTitle = "";
        await fetchTasks();
      }
    } catch (err) {
      console.error("Failed to add task:", err);
    }
  }

  async function completeTask(taskId: string) {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/tasks/${taskId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status_state: "completed" })
      });
      if (response.ok) {
        await fetchTasks();
      }
    } catch (err) {
      console.error("Failed to complete task:", err);
    }
  }

  async function deleteTask(taskId: string) {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/tasks/${taskId}`, {
        method: "DELETE"
      });
      if (response.ok) {
        await fetchTasks();
      }
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  }

  function formatDeadline(epoch: number): string {
    const now = Math.floor(Date.now() / 1000);
    const diff = epoch - now;
    if (diff < 0) return "Expired";
    const hours = Math.floor(diff / 3600);
    const mins = Math.floor((diff % 3600) / 60);
    if (hours > 0) return `${hours}h ${mins}m left`;
    return `${mins}m left`;
  }

  // Reactive trigger to fetch tasks on dashboard open
  $: if (showDashboard) {
    fetchTasks();
  }

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
    fetchPets();
    ws = new CompanionWebSocket(
      (state) => {
        companionState = state;
        fetchPets();
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
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  });
</script>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- MAIN LAYOUT                                                    -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<main class="w-screen h-screen flex flex-col items-center justify-start p-2 mt-[60px]"
      style="--ui-opacity: {uiOpacity / 100};">

  <!-- Sprite Container (Draggable) -->
  <div class="sprite-container">
       
    <!-- The actual Sprite (SVG or Canvas) -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="pet-sprite {animClass}" on:pointerdown={handlePointerDown} on:pointermove={handlePointerMove} on:pointerup={handlePointerUp} style="opacity: var(--ui-opacity); cursor: grab; background: rgba(1,1,1,0.01); border-radius: 50%;">
      {#if selectedPetId === "default_drone"}
        <svg width="128" height="128" viewBox="0 0 128 128" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="64" cy="64" r="50" fill="#1e293b" stroke="#334155" stroke-width="4"/>
          <circle cx="64" cy="64" r="35" fill="#0f172a"/>
          <!-- Visor -->
          <rect x="40" y="55" width="48" height="14" rx="7" fill="#38bdf8" />
          <rect x="45" y="58" width="38" height="8" rx="4" fill="#e0f2fe" />
          <!-- Details -->
          <circle cx="64" cy="35" r="4" fill="#ef4444"/>
        </svg>
      {/if}
      <canvas bind:this={petCanvas} width="128" height="128"></canvas>
    </div>
         
    <!-- Dialogue Bubble (Shows if typing, critical, dashboard closed, or playing in play tab) -->
    {#if displayedDialogue && (!showDashboard || activeTab === 'interact' || companionState.display_animation_frame === 'nagging_severe')}
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

      <!-- Tab Controls -->
      <div class="tabs-row">
        <button class="tab-btn" class:active={activeTab === 'core'} on:click={() => activeTab = 'core'}>📊 Core</button>
        <button class="tab-btn" class:active={activeTab === 'tasks'} on:click={() => { activeTab = 'tasks'; fetchTasks(); }}>🎯 Tasks ({companionState.active_tasks_count})</button>
        <button class="tab-btn" class:active={activeTab === 'interact'} on:click={() => activeTab = 'interact'}>🧸 Play</button>
      </div>

      {#if activeTab === 'core'}
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
      {:else if activeTab === 'tasks'}
        <!-- ─── Tasks Section ────────────────────────────────────── -->
        <div class="tasks-section">
          <!-- Add Task Form -->
          <div class="add-task-form">
            <input type="text" placeholder="New task title..." bind:value={newTaskTitle} class="task-input" on:keydown={(e) => e.key === 'Enter' && addTask()} />
            <div class="form-row">
              <select bind:value={newTaskPriority} class="task-select">
                <option value="low">Low Priority</option>
                <option value="medium">Medium Priority</option>
                <option value="high">High Priority</option>
                <option value="critical">Critical</option>
              </select>
              <select bind:value={newTaskDeadlineHours} class="task-select">
                <option value={0.5}>30 Mins</option>
                <option value={1}>1 Hour</option>
                <option value={2}>2 Hours</option>
                <option value={4}>4 Hours</option>
                <option value={8}>8 Hours</option>
                <option value={24}>24 Hours</option>
              </select>
              <button class="add-btn" on:click={addTask}>Add</button>
            </div>
          </div>

          <!-- Tasks List -->
          <div class="tasks-list">
            {#if tasks.length === 0}
              <div class="empty-state">No tasks created yet.</div>
            {:else}
              {#each tasks as task (task.task_id)}
                <div class="task-item" class:task-completed={task.status_state === 'completed'} class:task-failed={task.status_state === 'failed'}>
                  <div class="task-info">
                    <div class="task-title-row">
                      <span class="badge badge-{task.priority_level}">{task.priority_level}</span>
                      <span class="task-title" title={task.clean_title}>{task.clean_title}</span>
                    </div>
                    <div class="task-meta-row">
                      <span class="task-status status-{task.status_state}">{task.status_state}</span>
                      <span class="task-deadline">{formatDeadline(task.deadline_epoch)}</span>
                    </div>
                  </div>
                  <div class="task-actions">
                    {#if task.status_state === 'pending' || task.status_state === 'active'}
                      <button class="task-action-btn complete-btn" on:click={() => completeTask(task.task_id)} title="Complete Task">✓</button>
                    {/if}
                    <button class="task-action-btn delete-btn" on:click={() => deleteTask(task.task_id)} title="Remove Task">✕</button>
                  </div>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      {:else}
        <!-- Play / Interaction Section -->
        <div class="interact-section">
          <div class="section-title flex items-center justify-between mb-3 border-b border-white/5 pb-1">
            <span class="text-xs font-mono font-bold tracking-wider text-slate-300">PLAY & CARE</span>
            <span class="text-[10px] text-slate-500 font-mono">LVL {companionState.current_level}</span>
          </div>
          
          <div class="interact-grid">
            <button class="interact-card" on:click={() => interact("pet")}>
              <div class="icon">👋</div>
              <div class="details">
                <span class="title">Pet Companion</span>
                <span class="reward">+10 XP</span>
              </div>
            </button>
            
            <button class="interact-card" on:click={() => interact("feed")}>
              <div class="icon">🍖</div>
              <div class="details">
                <span class="title">Feed Treat</span>
                <span class="reward">+25 XP</span>
              </div>
            </button>
          </div>
          
          <div class="interact-footer flex flex-col gap-1 border-t border-white/5 pt-2 text-[10px] text-slate-400 font-mono mt-auto">
            <div class="flex justify-between">
              <span>EXP points:</span>
              <span class="text-indigo-400 font-bold">{companionState.experience_progress_percentage}% ({companionState.evolution_stage})</span>
            </div>
            <div class="progress-track" style="margin-top: 2px;">
              <div class="progress-fill xp-bar-fill" style="width: {companionState.experience_progress_percentage}%;"></div>
            </div>
          </div>
        </div>
      {/if}

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
    position: relative;
    width: 128px;
    height: 128px;
    object-fit: contain;
    filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5));
    transition: filter 0.3s ease, transform 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .pet-sprite svg {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 1;
    pointer-events: none;
  }
  .pet-sprite canvas {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 2;
    width: 128px;
    height: 128px;
    image-rendering: -moz-crisp-edges;
    image-rendering: -webkit-crisp-edges;
    image-rendering: pixelated;
    image-rendering: crisp-edges;
    pointer-events: none;
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

  /* ─── Task Manager Styles ──────────────────────────────────── */
  .tabs-row {
    display: flex;
    border-bottom: 1px solid var(--cp-border);
    background: rgba(255, 255, 255, 0.02);
  }
  .tab-btn {
    flex: 1;
    padding: 10px;
    font-size: 11px;
    font-family: var(--cp-font-mono);
    text-align: center;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--cp-text-secondary);
    cursor: pointer;
    transition: all 0.2s;
  }
  .tab-btn:hover {
    color: var(--cp-text-primary);
    background: rgba(255, 255, 255, 0.04);
  }
  .tab-btn.active {
    color: var(--cp-accent-glow);
    border-bottom-color: var(--cp-accent);
    background: rgba(99, 102, 241, 0.08);
  }

  .tasks-section {
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 420px;
    overflow: hidden;
  }

  .add-task-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--cp-border);
    border-radius: var(--cp-radius-sm);
    padding: 10px;
  }

  .task-input {
    width: 100%;
    background: var(--cp-bg-input);
    border: 1px solid var(--cp-border);
    border-radius: var(--cp-radius-xs);
    padding: 6px 10px;
    color: var(--cp-text-primary);
    font-size: 12px;
    outline: none;
    transition: border-color 0.2s;
  }
  .task-input:focus {
    border-color: var(--cp-border-active);
  }

  .form-row {
    display: flex;
    gap: 8px;
  }

  .task-select {
    flex: 1;
    background: var(--cp-bg-input);
    border: 1px solid var(--cp-border);
    border-radius: var(--cp-radius-xs);
    padding: 4px 6px;
    color: var(--cp-text-primary);
    font-size: 11px;
    outline: none;
  }

  .add-btn {
    background: var(--cp-accent);
    color: white;
    border: none;
    border-radius: var(--cp-radius-xs);
    padding: 4px 14px;
    font-size: 11px;
    font-family: var(--cp-font-mono);
    cursor: pointer;
    transition: background 0.2s;
  }
  .add-btn:hover {
    background: var(--cp-accent-glow);
  }

  .tasks-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    max-height: 240px;
    padding-right: 4px;
  }

  .empty-state {
    text-align: center;
    font-size: 12px;
    color: var(--cp-text-muted);
    padding: 30px 0;
  }

  .task-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--cp-border);
    border-radius: var(--cp-radius-sm);
    padding: 8px 12px;
    gap: 12px;
    transition: all 0.2s;
  }
  .task-item:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: var(--cp-border-active);
  }
  .task-completed {
    opacity: 0.6;
    background: rgba(16, 185, 129, 0.02);
  }
  .task-failed {
    opacity: 0.7;
    background: rgba(239, 68, 68, 0.02);
    border-color: rgba(239, 68, 68, 0.15);
  }

  .task-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    min-width: 0;
  }

  .task-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .task-title {
    font-size: 12px;
    font-weight: 500;
    color: var(--cp-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .task-completed .task-title {
    text-decoration: line-through;
    color: var(--cp-text-muted);
  }

  .task-meta-row {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 10px;
    color: var(--cp-text-secondary);
  }

  .task-status {
    text-transform: uppercase;
    font-family: var(--cp-font-mono);
    font-weight: 600;
  }
  .status-active { color: var(--cp-accent-glow); }
  .status-pending { color: var(--cp-text-secondary); }
  .status-completed { color: var(--cp-accent-success); }
  .status-failed { color: var(--cp-accent-danger); }

  .task-deadline {
    font-family: var(--cp-font-mono);
    color: var(--cp-text-muted);
  }

  .task-actions {
    display: flex;
    gap: 6px;
  }

  .task-action-btn {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--cp-radius-xs);
    border: 1px solid var(--cp-border);
    background: var(--cp-bg-input);
    color: var(--cp-text-primary);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .complete-btn:hover {
    background: var(--cp-accent-success);
    border-color: var(--cp-accent-success);
    color: white;
  }
  .delete-btn:hover {
    background: var(--cp-accent-danger);
    border-color: var(--cp-accent-danger);
    color: white;
  }

  /* ─── Play / Interaction Tab Styles ────────────────────────── */
  .interact-section {
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 380px;
    overflow: hidden;
  }
  .interact-grid {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .interact-card {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--cp-border);
    border-radius: var(--cp-radius-sm);
    padding: 12px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
    width: 100%;
    color: var(--cp-text-primary);
    outline: none;
  }
  .interact-card:hover {
    background: rgba(99, 102, 241, 0.08);
    border-color: var(--cp-accent);
    transform: translateY(-1px);
  }
  .interact-card:active {
    transform: translateY(0);
  }
  .interact-card .icon {
    font-size: 20px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .interact-card:hover .icon {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.3);
  }
  .interact-card .details {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .interact-card .title {
    font-size: 12px;
    font-weight: 600;
  }
  .interact-card .reward {
    font-size: 10px;
    font-family: var(--cp-font-mono);
    color: var(--cp-accent-glow);
    font-weight: 500;
  }
</style>
