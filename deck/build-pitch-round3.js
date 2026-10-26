const pptxgen = require("pptxgenjs");
const path = require("path");
const SKILL = "C:/Users/Tarun S/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin/c8b42d6b-e842-4a88-8e8a-c218bdce7852/8edae868-47db-4e1a-aa54-d65681e832b4/skills/pptx";
const { applyTheme } = require(path.join(SKILL, "scripts/apply_theme.js"));
const OUT = process.argv[2];

const THEME = {
  name: "Potential", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "14171B", lt1: "FFFFFF", dk2: "70777F", lt2: "F5F5F3",
    accent1: "B4472E", accent2: "2E6A4F", accent3: "14171B", accent4: "70777F",
    accent5: "D7D9DD", accent6: "F5F5F3", hlink: "B4472E", folHlink: "70777F" },
};
const MONO = "Courier New";
const INK = "14171B", MUTED = "70777F", FAINT = "9DA3AA", ACCENT = "B4472E",
      GREEN = "2E6A4F", RULE = "E2E4E7", TINT = "F5F5F3", PAPER = "FFFFFF";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Team Potential";
pres.company = "Team Potential";
pres.title = "AI Investigation Assistant";

const W = 13.333, H = 7.5, M = 1.0, CW = W - M * 2;

pres.defineSlideMaster({ title: "DARK", background: { color: INK }, objects: [] });
pres.defineSlideMaster({
  title: "LIGHT", background: { color: PAPER },
  objects: [{ placeholder: { options: {
    name: "title", type: "title", x: M, y: 0.72, w: CW, h: 0.8,
    fontSize: 33, color: INK, fontFace: "Cambria", align: "left",
    valign: "middle", margin: 0 }, text: "" } }],
  slideNumber: { x: W - M - 0.35, y: H - 0.56, w: 0.35, h: 0.26,
    fontSize: 9.5, color: "C7CACE", align: "right", fontFace: "Calibri" },
});

const eyebrow = (s, t, c = ACCENT) => s.addText(t.toUpperCase(), {
  x: M, y: 0.4, w: CW, h: 0.24, isTextBox: true, margin: 0,
  fontSize: 10, bold: true, charSpacing: 2.4, color: c, fontFace: "Calibri" });
const hr = (s, y, x = M, w = CW, c = RULE, h = 0.01) =>
  s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: c }, line: { width: 0 } });

// ============================================== 1 OVERVIEW
{
  pres.addSection({ title: "Overview" });
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Overview" });
  s.addText("TEAM POTENTIAL", { x: M, y: 1.72, w: CW, h: 0.28, isTextBox: true,
    margin: 0, fontSize: 11.5, bold: true, charSpacing: 3.2, color: ACCENT, fontFace: "Calibri" });
  s.addText("AI Investigation Assistant", { x: M, y: 2.16, w: CW, h: 0.95,
    isTextBox: true, margin: 0, fontSize: 52, color: PAPER, fontFace: "Cambria" });
  s.addText("Paste a failing log. Get the root cause, the evidence behind it and the fix — then ask it anything about the incident.",
    { x: M, y: 3.2, w: 11.0, h: 0.66, isTextBox: true, margin: 0,
      fontSize: 16.5, color: "A8AEB5", fontFace: "Calibri" });
  hr(s, 4.3, M, 2.6, "363B41");
  s.addText([
    { text: "An LLM that cannot get the diagnosis wrong,", options: { color: PAPER, bold: true } },
    { text: "  because it is never the one deciding.", options: { color: ACCENT } },
  ], { x: M, y: 4.56, w: 11.2, h: 0.42, isTextBox: true, margin: 0,
       fontSize: 19, fontFace: "Cambria" });
  s.addText("LEAP Young Innovators 2026   ·   Theme 3, Log Analysis   ·   Société Générale",
    { x: M, y: 6.3, w: CW, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 12, color: "6A7179", fontFace: "Calibri" });
  s.addNotes("20s. Team Potential. Paste a log, get the cause with evidence, then interrogate it. " +
    "The bottom line is the thesis — I'll show you the mechanism in two slides.");
}

// ============================================== 2 PROBLEM
{
  pres.addSection({ title: "Problem" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Problem" });
  eyebrow(s, "The problem");
  s.addText("Seven consoles, and often still no answer", { placeholder: "title" });
  s.addText("One failure, seven systems checked by hand, each in a different tool.",
    { x: M, y: 1.66, w: 10.6, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });
  ["Windows Service", "Aldavar DB", "Database views", "Galileo",
   "ALD SAT endpoints", "Network", "Application logs"].forEach((c, i) => {
    const x = M + i * 1.62;
    s.addText(String(i + 1).padStart(2, "0"), { x, y: 2.4, w: 1.45, h: 0.24,
      isTextBox: true, margin: 0, fontSize: 10, color: FAINT, fontFace: MONO });
    s.addText(c, { x, y: 2.66, w: 1.5, h: 0.6, isTextBox: true, margin: 0,
      fontSize: 12.5, color: INK, fontFace: "Calibri" });
  });
  hr(s, 3.42);
  s.addText("Every check passes. The sync is still broken.", { x: M, y: 3.74, w: 7.9,
    h: 0.48, isTextBox: true, margin: 0, fontSize: 24, color: INK, fontFace: "Cambria" });
  s.addText("The checklist completes and has nothing left to say. The cause is often never found — only worked around — and whatever was learned leaves with the person who learned it.",
    { x: M, y: 4.3, w: 7.2, h: 1.0, isTextBox: true, margin: 0,
      fontSize: 14, color: MUTED, fontFace: "Calibri" });
  s.addText("DAYS", { x: 9.1, y: 3.6, w: 3.2, h: 0.95, isTextBox: true, margin: 0,
    fontSize: 54, color: ACCENT, fontFace: "Cambria" });
  s.addText("of engineer time per incident, across three teams.",
    { x: 9.1, y: 4.6, w: 3.23, h: 0.7, isTextBox: true, margin: 0,
      fontSize: 12.5, color: MUTED, fontFace: "Calibri" });
  s.addNotes("30s — move fast here, they saw this last round. Seven consoles, and the " +
    "checklist can finish and still leave you with nothing.");
}

// ============================================== 3 THE MECHANISM  (hero slide)
{
  pres.addSection({ title: "Mechanism" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Mechanism" });
  eyebrow(s, "How it works");
  s.addText("The LLM runs last, on an answer that already exists", { placeholder: "title" });

  const steps = [
    ["PASTE", "raw log"],
    ["PARSE", "typed facts"],
    ["RULES", "the cause"],
    ["GRAPH", "who owns it"],
    ["VECTOR", "seen before?"],
    ["ASSEMBLE", "full RCA"],
  ];
  const bw = 1.52, gap = 0.17, y = 2.26;
  steps.forEach(([t, d], i) => {
    const x = M + i * (bw + gap);
    s.addShape(pres.ShapeType.rect, { x, y, w: bw, h: 1.18, fill: { color: TINT },
      line: { width: 0 }, objectName: `step${i}` });
    s.addText(t, { x: x + 0.14, y: y + 0.2, w: bw - 0.28, h: 0.28, isTextBox: true,
      margin: 0, fontSize: 12, bold: true, charSpacing: 0.8,
      color: (i === 3 || i === 4) ? ACCENT : INK, fontFace: "Calibri" });
    s.addText(d, { x: x + 0.14, y: y + 0.52, w: bw - 0.28, h: 0.5, isTextBox: true,
      margin: 0, fontSize: 10.5, color: MUTED, fontFace: "Calibri" });
    if (i < 5) s.addText("›", { x: x + bw - 0.02, y: y + 0.36, w: 0.2, h: 0.4,
      isTextBox: true, margin: 0, fontSize: 16, color: FAINT, fontFace: "Calibri",
      align: "center" });
  });
  const lx = M + 6 * (bw + gap);
  s.addShape(pres.ShapeType.rect, { x: lx, y, w: W - M - lx, h: 1.18,
    fill: { color: INK }, line: { width: 0 }, objectName: "llm" });
  s.addText("LLM", { x: lx + 0.14, y: y + 0.2, w: 1.3, h: 0.28, isTextBox: true,
    margin: 0, fontSize: 12, bold: true, charSpacing: 0.8, color: ACCENT, fontFace: "Calibri" });
  s.addText("explains it", { x: lx + 0.14, y: y + 0.52, w: 1.3, h: 0.5, isTextBox: true,
    margin: 0, fontSize: 10.5, color: "A8AEB5", fontFace: "Calibri" });

  // the two cost brackets
  const detW = 6 * bw + 5 * gap;
  hr(s, 3.62, M, detW, "D5D7DB");
  s.addText("DETERMINISTIC   ·   1.7 ms   ·   0 TOKENS", { x: M, y: 3.72, w: detW, h: 0.26,
    isTextBox: true, margin: 0, fontSize: 10, bold: true, charSpacing: 1.4,
    color: MUTED, fontFace: "Calibri" });
  hr(s, 3.62, lx, W - M - lx, ACCENT, 0.014);
  s.addText("1 CALL" + String.fromCharCode(10) + "400 TOKENS", { x: lx, y: 3.72, w: W - M - lx, h: 0.46,
    isTextBox: true, margin: 0, fontSize: 9.5, bold: true, charSpacing: 0.7,
    lineSpacingMultiple: 1.1, color: ACCENT, fontFace: "Calibri" });

  hr(s, 4.34);
  const pts = [
    ["Rules, not a model, name the cause", "So a hallucination cannot become a diagnosis"],
    ["Graph and vectors enrich — never decide", "They run after the cause is already fixed"],
    ["Switch the LLM off and the answer is identical", "269 tests prove it, offline, with no key"],
  ];
  pts.forEach(([a, b], i) => {
    const x = M + i * 3.87;
    s.addText(a, { x, y: 4.6, w: 3.5, h: 0.6, isTextBox: true, margin: 0,
      fontSize: 14, bold: true, color: INK, fontFace: "Calibri" });
    s.addText(b, { x, y: 5.24, w: 3.5, h: 0.6, isTextBox: true, margin: 0,
      fontSize: 12, color: ACCENT, fontFace: "Calibri" });
  });

  s.addNotes("60s — THIS is the slide. Walk the arrow left to right. Paste, parse into " +
    "facts, rules name the cause, graph says who owns it, vectors find precedent, " +
    "assemble the RCA — all of that is 1.7 milliseconds and zero tokens. Only then does " +
    "the LLM run, once, capped at 400 tokens, on a finished answer. That ordering is the " +
    "whole invention.");
}

// ============================================== 4 GRAPH + VECTOR
{
  pres.addSection({ title: "Retrieval" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Retrieval" });
  eyebrow(s, "The two retrieval layers");
  s.addText("Relationships by traversal, precedent by similarity", { placeholder: "title" });

  // GRAPH
  s.addShape(pres.ShapeType.rect, { x: M, y: 1.84, w: 5.5, h: 3.0,
    fill: { color: TINT }, line: { width: 0 }, objectName: "graphCard" });
  s.addText("KNOWLEDGE GRAPH", { x: M + 0.36, y: 2.1, w: 4.8, h: 0.24, isTextBox: true,
    margin: 0, fontSize: 10, bold: true, charSpacing: 1.8, color: ACCENT, fontFace: "Calibri" });
  s.addText("56 nodes, 82 edges — built from the config at startup, no database.",
    { x: M + 0.36, y: 2.4, w: 4.8, h: 0.46, isTextBox: true, margin: 0,
      fontSize: 13, color: INK, fontFace: "Calibri" });
  s.addText("Incident  →  CLASSIFIED_AS  →  Layer", { x: M + 0.36, y: 2.96, w: 4.8, h: 0.26,
    isTextBox: true, margin: 0, fontSize: 11.5, color: MUTED, fontFace: MONO });
  s.addText("          →  OWNED_BY  →  Team", { x: M + 0.36, y: 3.22, w: 4.8, h: 0.26,
    isTextBox: true, margin: 0, fontSize: 11.5, color: ACCENT, fontFace: MONO });
  s.addText("“Which team owns this?” is two hops, not a model recalling something. Same for what the application calls and depends on.",
    { x: M + 0.36, y: 3.66, w: 4.8, h: 0.78, isTextBox: true, margin: 0,
      fontSize: 12.5, color: MUTED, fontFace: "Calibri" });

  // VECTOR
  s.addShape(pres.ShapeType.rect, { x: 6.83, y: 1.84, w: 5.5, h: 3.0,
    fill: { color: TINT }, line: { width: 0 }, objectName: "vecCard" });
  s.addText("VECTOR SEARCH", { x: 7.19, y: 2.1, w: 4.8, h: 0.24, isTextBox: true,
    margin: 0, fontSize: 10, bold: true, charSpacing: 1.8, color: ACCENT, fontFace: "Calibri" });
  s.addText("Cosine similarity over a normalised failure signature — never the raw stack trace.",
    { x: 7.19, y: 2.4, w: 4.8, h: 0.46, isTextBox: true, margin: 0,
      fontSize: 13, color: INK, fontFace: "Calibri" });
  s.addText("Same fault, written up in different words:", { x: 7.19, y: 2.96, w: 4.8, h: 0.26,
    isTextBox: true, margin: 0, fontSize: 11.5, color: MUTED, fontFace: "Calibri" });
  s.addText([
    { text: "keyword match  0.13", options: { color: FAINT } },
    { text: "        vectors  0.69", options: { color: ACCENT, bold: true } },
  ], { x: 7.19, y: 3.22, w: 4.8, h: 0.28, isTextBox: true, margin: 0,
       fontSize: 12.5, fontFace: MONO });
  s.addText("Keyword matching misses it entirely. Vectors recognise it — and every signature is embedded once, then cached forever.",
    { x: 7.19, y: 3.66, w: 4.8, h: 0.78, isTextBox: true, margin: 0,
      fontSize: 12.5, color: MUTED, fontFace: "Calibri" });

  hr(s, 5.22);
  s.addText("Neither of them decides anything.", { x: M, y: 5.46, w: 11.0, h: 0.42,
    isTextBox: true, margin: 0, fontSize: 19, color: INK, fontFace: "Cambria" });
  s.addText("The cause is already fixed before either runs. Retrieval only adds context — who to call, and whether this has bitten us before. A wrong retrieval gives you a less useful answer, never a wrong one.",
    { x: M, y: 5.92, w: 11.0, h: 0.66, isTextBox: true, margin: 0,
      fontSize: 13.5, color: MUTED, fontFace: "Calibri" });
  s.addNotes("55s. Two retrieval layers, two jobs. Graph for relationships — traversal, no " +
    "vectors. Vector search for precedent — embeddings, no graph. The 0.13 versus 0.69 " +
    "is the same fault described differently: keyword matching misses it, vectors catch " +
    "it. Close on the bottom line — neither one decides.");
}

// ============================================== 5 TWO MODES
{
  pres.addSection({ title: "Ask" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Ask" });
  eyebrow(s, "Ask the diagnosis");
  s.addText("Both modes get the incident. Only one may speculate", { placeholder: "title" });
  s.addText("The finished RCA is fed in as context, so the assistant is always talking about this failure — not answering in the abstract.",
    { x: M, y: 1.64, w: 11.2, h: 0.56, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const modes = [
    [M, "PROJECT  ·  GROUNDED", GREEN,
     "May use nothing but verified project data.",
     ["19 approved lookups, graph and vector results",
      "Every answer shows its source",
      "Says “I don’t have the evidence” rather than guessing"],
     "“Which team owns this?”"],
    [6.83, "GENERAL  ·  ADVISORY", ACCENT,
     "May reason beyond the facts — and must say when it does.",
     ["Same incident context, wider technical knowledge",
      "Marks every suggestion as suggestion",
      "Still useful when the engine returns Unknown"],
     "“What else could cause this?”"],
  ];
  modes.forEach(([x, head, col, lead, bullets, ex]) => {
    s.addShape(pres.ShapeType.rect, { x, y: 2.44, w: 5.5, h: 2.86,
      fill: { color: TINT }, line: { width: 0 }, objectName: "m" + x });
    s.addText(head, { x: x + 0.36, y: 2.7, w: 4.8, h: 0.24, isTextBox: true, margin: 0,
      fontSize: 10, bold: true, charSpacing: 1.8, color: col, fontFace: "Calibri" });
    s.addText(lead, { x: x + 0.36, y: 3.0, w: 4.8, h: 0.46, isTextBox: true, margin: 0,
      fontSize: 13, bold: true, color: INK, fontFace: "Calibri" });
    bullets.forEach((b, i) => s.addText("— " + b, { x: x + 0.36, y: 3.54 + i * 0.4,
      w: 4.8, h: 0.38, isTextBox: true, margin: 0, fontSize: 12, color: MUTED,
      fontFace: "Calibri" }));
    s.addText(ex, { x: x + 0.36, y: 4.84, w: 4.8, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 12, italic: true, color: col, fontFace: "Cambria" });
  });

  hr(s, 5.66);
  s.addText([
    { text: "A new joiner can ask the system instead of a colleague. ", options: { bold: true, color: INK } },
    { text: "The dependency chain comes from the topology graph, so the answer is the real one. Internal hostnames are masked before any prompt leaves the machine.",
      options: { color: MUTED } },
  ], { x: M, y: 5.88, w: 11.2, h: 0.66, isTextBox: true, margin: 0,
       fontSize: 13.5, fontFace: "Calibri" });
  s.addNotes("55s. Both modes receive the finished RCA as context — that is new. The " +
    "difference is permission, not data: Project may not go beyond the verified facts, " +
    "General may and has to flag it. General stays useful on a failure class nobody has " +
    "configured yet, which is the honest answer to 'what about something new'.");
}

// ============================================== 6 WHY IT WINS
{
  pres.addSection({ title: "Why" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Why" });
  eyebrow(s, "Why this is different");
  s.addText("Everyone can call an LLM. That isn’t the hard part", { placeholder: "title" });

  s.addText("TYPICAL LOG-ANALYSIS TOOL", { x: M, y: 1.72, w: 4.9, h: 0.24, isTextBox: true,
    margin: 0, fontSize: 9.5, bold: true, charSpacing: 1.6, color: FAINT, fontFace: "Calibri" });
  s.addText("THIS", { x: 6.5, y: 1.72, w: 5.8, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 9.5, bold: true, charSpacing: 1.6, color: ACCENT, fontFace: "Calibri" });
  hr(s, 2.0, M, 4.9, "E8EAEC");
  hr(s, 2.0, 6.5, 5.83, ACCENT, 0.014);

  const rows = [
    ["Asks the model what broke", "Rules decide; the model is never asked",
     "Hallucination cannot reach the diagnosis"],
    ["Answers even when it should not", "Returns “Inconclusive” and shows its working",
     "Silence beats a confident wrong answer at 2am"],
    ["Hardcoded to one system", "Four JSON files: topology, rules, runbooks, history",
     "Another team adapts it without writing code"],
    ["An LLM call per log, every time", "One call per incident, capped at 400 tokens",
     "Routing 8 of 8 common questions with zero calls"],
    ["Breaks when the API is down", "Runs with the AI switched off entirely",
     "269 tests pass with no key and no network"],
  ];
  rows.forEach(([a, b, c], i) => {
    const y = 2.22 + i * 0.84;
    s.addText(a, { x: M, y: y + 0.04, w: 4.9, h: 0.5, isTextBox: true, margin: 0,
      fontSize: 13, color: FAINT, fontFace: "Calibri" });
    s.addText(b, { x: 6.5, y, w: 5.83, h: 0.34, isTextBox: true, margin: 0,
      fontSize: 13.5, bold: true, color: INK, fontFace: "Calibri" });
    s.addText(c, { x: 6.5, y: y + 0.34, w: 5.83, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 11.5, color: ACCENT, fontFace: "Calibri" });
  });
  hr(s, 6.52);
  s.addText("The reliability is structural, not a prompt we tuned — and the portability is config, not a rewrite.",
    { x: M, y: 6.72, w: 10.75, h: 0.42, isTextBox: true, margin: 0,
      fontSize: 14.5, italic: true, color: INK, fontFace: "Cambria" });
  s.addNotes("70s — slow here. Read the right column aloud. Row three is adaptability: " +
    "all domain knowledge is four JSON files, so another team points it at their own " +
    "system by editing them. Row four is the cost story. Finish on the closing line.");
}

// ============================================== 7 PROOF + CLOSE
{
  pres.addSection({ title: "Close" });
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Close" });
  s.addText("BEYOND THE FIX", { x: M, y: 0.78, w: CW, h: 0.28, isTextBox: true, margin: 0,
    fontSize: 10.5, bold: true, charSpacing: 2.8, color: ACCENT, fontFace: "Calibri" });
  s.addText("Every incident makes the next one cheaper", { x: M, y: 1.18, w: 11.0, h: 0.66,
    isTextBox: true, margin: 0, fontSize: 32, color: PAPER, fontFace: "Cambria" });

  [["STOP IT RECURRING",
    "Actions across code, config, monitoring and process — with the safe batch size calculated from the throughput measured in the log."],
   ["WHAT NOT TO DO",
    "An explicit do-not list. “Do not raise the client timeout” — the client was never what cut the connection. This is where hours go."],
   ["WHY IT WAS HARD TO FIND",
    "It scores our own logging, 5 of 10. We never record how long a job takes, which is why a sync degrading for weeks stayed invisible."],
  ].forEach(([h, b], i) => {
    const x = M + i * 3.87;
    s.addText(h, { x, y: 2.16, w: 3.5, h: 0.26, isTextBox: true, margin: 0,
      fontSize: 9.5, bold: true, charSpacing: 1.6, color: ACCENT, fontFace: "Calibri" });
    hr(s, 2.5, x, 3.5, "34393F");
    s.addText(b, { x, y: 2.64, w: 3.5, h: 1.5, isTextBox: true, margin: 0,
      fontSize: 12.5, color: "A8AEB5", fontFace: "Calibri" });
  });

  hr(s, 4.4, M, CW, "34393F");
  [["269", "tests, offline"], ["1.7 ms", "to a diagnosis"], ["4", "config files"],
   ["0", "AI in the decision"]].forEach(([n, l], i) => {
    const x = M + i * 2.87;
    s.addText(n, { x, y: 4.66, w: 2.7, h: 0.8, isTextBox: true, margin: 0,
      fontSize: 40, color: PAPER, fontFace: MONO });
    s.addText(l, { x, y: 5.48, w: 2.7, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 12, color: "787F87", fontFace: "Calibri" });
  });

  s.addText("Next: the bank’s approved Azure OpenAI endpoint — one file changes.",
    { x: M, y: 6.0, w: 11.0, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 12, color: "6A7179", fontFace: "Calibri" });
  s.addText("Evidence decides what happened. The model explains it.", { x: M, y: 6.4,
    w: 8.0, h: 0.42, isTextBox: true, margin: 0, fontSize: 19, italic: true,
    color: PAPER, fontFace: "Cambria" });
  s.addText("TEAM POTENTIAL", { x: W - M - 3.0, y: 6.5, w: 3.0, h: 0.28, isTextBox: true,
    margin: 0, fontSize: 11.5, bold: true, charSpacing: 2.6, color: ACCENT,
    fontFace: "Calibri", align: "right" });
  s.addNotes("45s then straight into the demo. Three things beyond the fix, then the " +
    "numbers. 269 tests offline says it is real; 1.7 milliseconds says it scales; " +
    "four config files says anyone can adopt it; zero AI in the decision is the thesis. " +
    "Close on the line and start the demo.");
}

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
  console.log("wrote " + OUT);
});
