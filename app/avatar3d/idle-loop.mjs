// Visible, awake Jinx keeps smooth motion. The skull owns full resource sleep.
export const DEFAULTS = { interaction: 1800, fps: { active: 30, idle: 30 } };

// Ignore obsolete rest/sleep settings; no awake tier may drop below 30 fps.
export function ladderOptions(settings = {}) {
 const o = { ...DEFAULTS, fps: { ...DEFAULTS.fps } };
 const interaction = Number(settings.interaction);
 if (Number.isFinite(interaction) && interaction > 0) o.interaction = interaction;
 for (const tier of ['active','idle']) {
  const value = Number(settings[tier+'FPS']);
  if (Number.isFinite(value) && value > 0) o.fps[tier] = Math.min(60, Math.max(30, value));
 }
 return o;
}

export class RenderGate {
 constructor(options = {}) {
  this.o = ladderOptions({interaction:options.interaction,
    activeFPS:options.fps?.active,idleFPS:options.fps?.idle});
  this.running = false; this.reason = 'init'; this.lastActivityAt = null;
 }
 evaluate(s = {}, now = 0) {
  if (this.lastActivityAt === null) this.lastActivityAt = now;
  const interacting = s.interactionAt != null && now >= s.interactionAt &&
                      now - s.interactionAt < this.o.interaction;
  const active = !!(s.busy || s.ptt || s.conversation || s.speaking || s.subtitles || interacting);
  if (active) this.wake(now);
  if (!s.ready) return this.#set(false, 'not-ready');
  if (s.hidden) return this.#set(false, 'hidden');
  if (s.suspended) return this.#set(false, 'suspended');
  if (s.paused) return this.#set(false, 'paused');
  return this.#set(true, active ? 'active' : 'idle');
 }
 wake(now = 0) { this.lastActivityAt = now; }
 #set(running, reason) {
  const changed = running !== this.running || reason !== this.reason;
  this.running = running; this.reason = reason;
  return {running, reason, changed, fps: running ? this.o.fps[reason] : null};
 }
}

export function pollDelay({ hidden, busy, ptt } = {}) {
 if (hidden) return 4000;
 return busy || ptt ? 90 : 900;
}
export function ringDelay({ drawing, busy, ptt } = {}) {
 if (!drawing) return null;
 return (busy || ptt) ? 33 : 250;
}
