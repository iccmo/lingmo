/**
 * Client-side text analysis — density & force field (文档 §28-29).
 * Zero API calls. Runs in browser.
 */

export interface DensityReport {
  totalChars: number;
  expectationCount: number;
  density: number;        // expectations per 100 chars
  perParagraph: Array<{ chars: number; expectations: number; density: number }>;
}

export interface ForceReport {
  compression: number;    // 0-1: historical weight per char
  tension: number;        // 0-1: unsatisfied expectations
  torque: number;         // 0-1: expectation reversals
  resonance: number;      // 0-1: repeated elements significance
}

/**
 * Emotional unit density analysis (§28).
 * Counts expectation signals: but/yet/however (contradiction),
 * question marks (uncertainty), ellipsis (trailing), exclamation (surprise),
 * negation (reversal).
 */
export function analyzeDensity(text: string): DensityReport {
  const paragraphs = text.split(/\n\n+/).filter(p => p.trim());
  let totalExpectations = 0;

  const perParagraph = paragraphs.map(p => {
    const trimmed = p.trim();
    const chars = trimmed.length;
    // Count expectation-creating patterns
    const contradictions = (trimmed.match(/但是|可是|然而|却|不过|只是|but|yet|however/gi) || []).length;
    const questions = (trimmed.match(/[？?]/g) || []).length;
    const suspensions = (trimmed.match(/…|\.\.\./g) || []).length;
    const surprises = (trimmed.match(/[！!]/g) || []).length;
    const negations = (trimmed.match(/不是|没有|不会|不能|从未|not|never|no/gi) || []).length;

    const expectations = contradictions + questions + suspensions + surprises + negations;
    totalExpectations += expectations;

    return {
      chars,
      expectations,
      density: chars > 0 ? +(expectations / (chars / 100)).toFixed(1) : 0,
    };
  });

  return {
    totalChars: text.length,
    expectationCount: totalExpectations,
    density: text.length > 0 ? +(totalExpectations / (text.length / 100)).toFixed(1) : 0,
    perParagraph,
  };
}

/**
 * Four-force field analysis (§29).
 */
export function analyzeForces(text: string, historyWeight = 0): ForceReport {
  const sentences = text.split(/[。！？.!?\n]+/).filter(s => s.trim());

  // Compression: historical weight per meaningful unit
  const meaningfulChars = text.replace(/\s/g, '').length;
  const compression = Math.min(1, (historyWeight || sentences.length * 0.02) / Math.max(1, sentences.length * 0.1));

  // Tension: unsatisfied expectations
  let openQuestions = 0;
  let resolved = 0;
  for (const s of sentences) {
    if (s.match(/[？?]/)) openQuestions++;
    if (s.match(/原来|终于|原来如此|所以|于是|因此|是因为/)) resolved++;
  }
  const tension = Math.min(1, openQuestions / Math.max(1, openQuestions + resolved + 1));

  // Torque: expectation reversals
  const reversals = (text.match(/但是|可是|然而|却|不过|没想到|谁知|不料|竟然|居然|but|yet|however|unexpectedly/gi) || []).length;
  const torque = Math.min(1, reversals / Math.max(1, sentences.length * 0.1));

  // Resonance: repeated elements (2-4 char phrases appearing multiple times)
  const cleanText = text.replace(/[，。！？、；：""''「」『』\s]/g, '');
  const phrases: Record<string, number> = {};
  for (let i = 0; i < cleanText.length - 3; i++) {
    for (let len = 2; len <= 4; len++) {
      const phrase = cleanText.slice(i, i + len);
      if (phrase.length === len) {
        phrases[phrase] = (phrases[phrase] || 0) + 1;
      }
    }
  }
  const repeatedCount = Object.values(phrases).filter(c => c >= 3).length;
  const resonance = Math.min(1, repeatedCount / Math.max(1, sentences.length * 0.05));

  return { compression: +compression.toFixed(2), tension: +tension.toFixed(2), torque: +torque.toFixed(2), resonance: +resonance.toFixed(2) };
}

/**
 * Simple text quality summary combining both analyses.
 */
export function analyzeTextQuality(text: string): { density: DensityReport; forces: ForceReport; grade: string } {
  const density = analyzeDensity(text);
  const forces = analyzeForces(text);

  // Heuristic grade
  let score = 0;
  if (density.density >= 3) score += 3;
  else if (density.density >= 1.5) score += 2;
  else if (density.density >= 0.5) score += 1;

  if (forces.tension >= 0.4) score += 2;
  else if (forces.tension >= 0.2) score += 1;

  if (forces.torque >= 0.3) score += 2;
  else if (forces.torque >= 0.1) score += 1;

  if (forces.resonance >= 0.2) score += 1;

  const grade = score >= 7 ? 'S' : score >= 5 ? 'A' : score >= 3 ? 'B' : score >= 1 ? 'C' : 'D';

  return { density, forces, grade };
}
