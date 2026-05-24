/**
 * Sound Engine v3 — real audio files + synthesis fallback.
 * Place audio files in /public/audio/ambient/ and /public/audio/music/
 * If file exists → plays real loop. If not → falls back to Web Audio synthesis.
 */

type AmbientType = 'rain' | 'thunder' | 'campfire' | 'ocean' | 'forest' | 'wind' | 'cafe' | 'white';
type MusicMood = 'peaceful' | 'tense' | 'epic' | 'melancholy';

const AMBIENT_FILES: Record<AmbientType, string> = {
  rain: '/audio/ambient/rain.mp3',
  thunder: '/audio/ambient/thunder.mp3',
  campfire: '/audio/ambient/campfire.mp3',
  ocean: '/audio/ambient/ocean.mp3',
  forest: '/audio/ambient/forest.mp3',
  wind: '/audio/ambient/wind.mp3',
  cafe: '/audio/ambient/cafe.mp3',
  white: '/audio/ambient/white.mp3',
};

const MUSIC_FILES: Record<MusicMood, string> = {
  peaceful: '/audio/music/peaceful.mp3',
  tense: '/audio/music/tense.mp3',
  epic: '/audio/music/epic.mp3',
  melancholy: '/audio/music/melancholy.mp3',
};

interface ActiveLayer {
  audio?: HTMLAudioElement;
  ctx?: AudioContext;
  gain?: GainNode;
  nodes: Array<AudioNode | HTMLAudioElement>;
}

const ambient: ActiveLayer = { nodes: [] };
const music: ActiveLayer = { nodes: [] };

// ═══════════════ File checker ═══════════════

let fileExistsCache: Record<string, boolean> = {};

async function fileExists(url: string): Promise<boolean> {
  if (fileExistsCache[url] !== undefined) return fileExistsCache[url];
  try {
    const r = await fetch(url, { method: 'HEAD' });
    fileExistsCache[url] = r.ok;
    return r.ok;
  } catch {
    fileExistsCache[url] = false;
    return false;
  }
}

// ═══════════════ Public API ═══════════════

export async function startAmbient(type: AmbientType, volume: number) {
  stopAmbient();

  const filePath = AMBIENT_FILES[type];
  const exists = await fileExists(filePath);

  if (exists) {
    // ── Real audio file ──
    const audio = new Audio(filePath);
    audio.loop = true;
    audio.volume = Math.max(0, Math.min(1, volume));
    try { await audio.play(); } catch {}
    ambient.audio = audio;
    ambient.nodes = [audio];
  } else {
    // ── Fallback: synthesize ──
    synthesizeAmbient(type, volume);
  }
}

export function stopAmbient() {
  // HTML Audio
  if (ambient.audio) {
    ambient.audio.pause();
    ambient.audio.src = '';
    ambient.audio = undefined;
  }
  // Web Audio
  ambient.nodes.forEach(n => {
    try {
      if (n instanceof HTMLAudioElement) { n.pause(); n.src = ''; }
      if (n instanceof AudioBufferSourceNode) (n as AudioBufferSourceNode).stop();
      if (n instanceof OscillatorNode) (n as OscillatorNode).stop();
      (n as any).disconnect?.();
    } catch {}
  });
  ambient.nodes = [];
}

export function setAmbientVolume(volume: number) {
  const v = Math.max(0, Math.min(1, volume));
  if (ambient.audio) {
    ambient.audio.volume = v;
  } else if (ambient.gain) {
    ambient.gain.gain.value = v;
  }
}

// ═══════════════ Music ═══════════════

export async function startMusic(mood: MusicMood | null, volume: number) {
  stopMusic();
  if (!mood) return;

  const filePath = MUSIC_FILES[mood];
  const exists = await fileExists(filePath);

  if (exists) {
    const audio = new Audio(filePath);
    audio.loop = true;
    audio.volume = Math.max(0, Math.min(0.35, volume * 0.35));
    try { await audio.play(); } catch {}
    music.audio = audio;
    music.nodes = [audio];
  } else {
    synthesizeMusic(mood, volume);
  }
}

export function stopMusic() {
  if (music.audio) {
    music.audio.pause();
    music.audio.src = '';
    music.audio = undefined;
  }
  music.nodes.forEach(n => {
    try {
      if (n instanceof HTMLAudioElement) { n.pause(); n.src = ''; }
      if (n instanceof AudioBufferSourceNode) (n as AudioBufferSourceNode).stop();
      if (n instanceof OscillatorNode) (n as OscillatorNode).stop();
      (n as any).disconnect?.();
    } catch {}
  });
  music.nodes = [];
}

export function setMusicVolume(volume: number) {
  const v = Math.max(0, Math.min(0.35, volume * 0.35));
  if (music.audio) {
    music.audio.volume = v;
  } else if (music.gain) {
    music.gain.gain.value = v;
  }
}

// ═══════════════ Synthesis fallback (same as v2) ═══════════════

function getCtx(): AudioContext {
  const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

function pinkNoise(ctx: AudioContext, seconds: number): AudioBuffer {
  const sr = ctx.sampleRate;
  const buf = ctx.createBuffer(1, sr * seconds, sr);
  const data = buf.getChannelData(0);
  let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
  for (let i = 0; i < data.length; i++) {
    const white = Math.random() * 2 - 1;
    b0 = 0.99886 * b0 + white * 0.0555179;
    b1 = 0.99332 * b1 + white * 0.0750759;
    b2 = 0.96900 * b2 + white * 0.1538520;
    b3 = 0.86650 * b3 + white * 0.3104856;
    b4 = 0.55000 * b4 + white * 0.5329522;
    b5 = -0.7616 * b5 - white * 0.0168980;
    data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
    b6 = white * 0.115926;
  }
  return buf;
}

function brownNoise(ctx: AudioContext, seconds: number): AudioBuffer {
  const sr = ctx.sampleRate;
  const buf = ctx.createBuffer(1, sr * seconds, sr);
  const data = buf.getChannelData(0);
  let prev = 0;
  for (let i = 0; i < data.length; i++) {
    prev = prev + (Math.random() * 2 - 1) * 0.012;
    if (prev > 1) prev = 1; else if (prev < -1) prev = -1;
    data[i] = prev * 0.7;
  }
  return buf;
}

function synthesizeAmbient(type: AmbientType, volume: number) {
  const ctx = getCtx();
  const masterGain = ctx.createGain();
  masterGain.gain.value = volume;
  ambient.gain = masterGain;
  const nodes: Array<AudioNode> = [masterGain];

  if (type === 'rain') {
    [400, 700, 1100, 1600].forEach((freq, i) => {
      const buf = pinkNoise(ctx, 5);
      const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
      const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 0.3; bp.frequency.value = freq;
      const lfo = ctx.createOscillator(); lfo.type = 'triangle'; lfo.frequency.value = 1.5 + i * 0.8;
      const lfoGain = ctx.createGain(); lfoGain.gain.value = 80 + i * 30;
      lfo.connect(lfoGain); lfoGain.connect(bp.frequency); lfo.start();
      const gain = ctx.createGain(); gain.gain.value = 0.08 - i * 0.01;
      src.connect(bp); bp.connect(gain); gain.connect(masterGain); src.start();
      nodes.push(src, bp, gain, lfo, lfoGain);
    });
  } else if (type === 'thunder') {
    const rumble = brownNoise(ctx, 6);
    const rSrc = ctx.createBufferSource(); rSrc.buffer = rumble; rSrc.loop = true;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 150;
    const rGain = ctx.createGain(); rGain.gain.value = 0.3;
    rSrc.connect(lp); lp.connect(rGain); rGain.connect(masterGain); rSrc.start();
    nodes.push(rSrc, lp, rGain);
  } else if (type === 'campfire') {
    const rumble = brownNoise(ctx, 4);
    const rSrc = ctx.createBufferSource(); rSrc.buffer = rumble; rSrc.loop = true;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 300;
    const rGain = ctx.createGain(); rGain.gain.value = 0.2;
    rSrc.connect(lp); lp.connect(rGain); rGain.connect(masterGain); rSrc.start();
    nodes.push(rSrc, lp, rGain);
  } else if (type === 'ocean') {
    const buf = brownNoise(ctx, 10);
    const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 500;
    src.connect(lp); lp.connect(masterGain); src.start();
    nodes.push(src, lp);
  } else if (type === 'forest' || type === 'wind') {
    const buf = pinkNoise(ctx, 5);
    const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = type === 'wind' ? 3000 : 2000;
    const gain = ctx.createGain(); gain.gain.value = 0.08;
    src.connect(lp); lp.connect(gain); gain.connect(masterGain); src.start();
    nodes.push(src, lp, gain);
  } else {
    const buf = pinkNoise(ctx, 3);
    const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
    const gain = ctx.createGain(); gain.gain.value = 0.06;
    src.connect(gain); gain.connect(masterGain); src.start();
    nodes.push(src, gain);
  }

  masterGain.connect(ctx.destination);
  ambient.nodes = nodes;
}

function synthesizeMusic(mood: MusicMood, volume: number) {
  const ctx = getCtx();
  const masterGain = ctx.createGain();
  masterGain.gain.value = Math.max(0, Math.min(0.35, volume * 0.35));
  music.gain = masterGain;
  const nodes: Array<AudioNode> = [masterGain];

  const chords: Record<MusicMood, number[]> = {
    peaceful: [130.8, 164.8, 196.0, 261.6, 329.6],
    tense: [55, 58.3, 110, 116.5],
    epic: [41.2, 82.4, 123.5, 165.0],
    melancholy: [220, 261.6, 329.6, 392.0],
  };

  chords[mood].forEach((f) => {
    const osc = ctx.createOscillator();
    osc.type = mood === 'tense' ? 'sawtooth' : 'sine';
    osc.frequency.value = f;
    const gain = ctx.createGain(); gain.gain.value = mood === 'tense' ? 0.04 : 0.06;
    osc.connect(gain); gain.connect(masterGain); osc.start();
    nodes.push(osc, gain);
  });

  masterGain.connect(ctx.destination);
  music.nodes = nodes;
}
