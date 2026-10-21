// Tab-open alerts: Web Audio beep + Notification API. These only fire while
// the site is open (even backgrounded) — never with the browser closed.

type Tone = 'sine' | 'square';

export function playTone(type: Tone = 'sine', freq = 880, seconds = 0.6, volume = 0.15): void {
  try {
    const Ctx =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    gain.gain.setValueAtTime(volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + seconds);
    osc.start();
    osc.stop(ctx.currentTime + seconds);
  } catch {
    /* Web Audio unsupported — skip the beep */
  }
}

export const notificationsSupported = (): boolean => 'Notification' in window;

export function desktopNotify(title: string, body: string): void {
  if (notificationsSupported() && Notification.permission === 'granted') {
    new Notification(title, { body });
  }
}

const ALERTS_KEY = 'drovery_alerts';
export const alertsPref = {
  get(): boolean {
    try {
      return localStorage.getItem(ALERTS_KEY) === 'on';
    } catch {
      return false;
    }
  },
  set(on: boolean): void {
    try {
      localStorage.setItem(ALERTS_KEY, on ? 'on' : 'off');
    } catch {
      /* ignore */
    }
  },
};
