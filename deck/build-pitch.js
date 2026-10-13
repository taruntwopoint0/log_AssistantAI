const pptxgen = require("pptxgenjs");
const path = require("path");
const SKILL = "C:/Users/Tarun S/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin/c8b42d6b-e842-4a88-8e8a-c218bdce7852/8edae868-47db-4e1a-aa54-d65681e832b4/skills/pptx";
const { applyTheme } = require(path.join(SKILL, "scripts/apply_theme.js"));
const OUT = process.argv[2];

const THEME = {
  name: "Potential",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "14171B", lt1: "FFFFFF", dk2: "70777F", lt2: "F5F5F3",
    accent1: "B4472E", accent2: "2E6A4F", accent3: "14171B",
    accent4: "70777F", accent5: "D7D9DD", accent6: "F5F5F3",
    hlink: "B4472E", folHlink: "70777F",
  },
};

const MONO = "Courier New";
const INK = "14171B", MUTED = "70777F", FAINT = "9DA3AA",
      ACCENT = "B4472E", RULE = "E2E4E7", TINT = "F5F5F3", PAPER = "FFFFFF";

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
    name: "title", type: "title", x: M, y: 0.74, w: CW, h: 0.82,
    fontSize: 34, color: INK, fontFace: "Cambria", align: "left",
    valign: "middle", margin: 0 }, text: "" } }],
  slideNumber: { x: W - M - 0.35, y: H - 0.58, w: 0.35, h: 0.26,
    fontSize: 9.5, color: "C7CACE", align: "right", fontFace: "Calibri" },
});

const eyebrow = (s, t, c = ACCENT) => s.addText(t.toUpperCase(), {
  x: M, y: 0.42, w: CW, h: 0.24, isTextBox: true, margin: 0,
  fontSize: 10, bold: true, charSpacing: 2.4, color: c, fontFace: "Calibri" });
const hr = (s, y, x = M, w = CW, c = RULE, h = 0.01) =>
  s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: c }, line: { width: 0 } });

// ================================================== 1 OVERVIEW
{
  pres.addSection({ title: "Overview" });
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Overview" });
  s.addText("TEAM POTENTIAL", { x: M, y: 1.6, w: CW, h: 0.28, isTextBox: true,
    margin: 0, fontSize: 11.5, bold: true, charSpacing: 3.2, color: ACCENT, fontFace: "Calibri" });
  s.addText("AI Investigation Assistant", { x: M, y: 2.05, w: CW, h: 0.95,
    isTextBox: true, margin: 0, fontSize: 52, color: PAPER, fontFace: "Cambria" });
  s.addText("Paste a failing log. Get the root cause, the evidence behind it, and the fix — then ask it questions.",
    { x: M, y: 3.06, w: 11.0, h: 0.66, isTextBox: true, margin: 0,
      fontSize: 17, color: "A8AEB5", fontFace: "Calibri" });
  hr(s, 4.05, M, 2.6, "363B41");
  s.addText([
    { text: "AI where language is the job.", options: { color: PAPER, bold: true } },
    { text: "  Measured evidence where the answer has to be right.", options: { color: ACCENT } },
  ], { x: M, y: 4.32, w: 11.0, h: 0.42, isTextBox: true, margin: 0,
       fontSize: 19, fontFace: "Cambria" });
  s.addText("LEAP Young Innovators 2026   ·   Theme 3, Log Analysis   ·   Société Générale",
    { x: M, y: 6.3, w: CW, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 12, color: "6A7179", fontFace: "Calibri" });
  s.addNotes("30s. We are Team Potential. Paste a failing log, get the root cause with the " +
    "evidence, then ask it follow-up questions. The line at the bottom is our principle: " +
    "the AI does the language, measured evidence does the judgement.");
}

// ================================================== 2 PROBLEM
{
  pres.addSection({ title: "Problem" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Problem" });
  eyebrow(s, "The problem");
  s.addText("Seven consoles, and often still no answer", { placeholder: "title" });
  s.addText("When the supplier sync fails, an engineer checks seven systems by hand. Each one is a different tool.",
    { x: M, y: 1.7, w: 10.6, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });
  ["Windows Service", "Aldavar DB", "Database views", "Galileo",
   "ALD SAT endpoints", "Network", "Application logs"].forEach((c, i) => {
    const x = M + i * 1.62;
    s.addText(String(i + 1).padStart(2, "0"), { x, y: 2.5, w: 1.45, h: 0.24,
      isTextBox: true, margin: 0, fontSize: 10, color: FAINT, fontFace: MONO });
    s.addText(c, { x, y: 2.76, w: 1.5, h: 0.6, isTextBox: true, margin: 0,
      fontSize: 12.5, color: INK, fontFace: "Calibri" });
  });
  hr(s, 3.5);
  s.addText("Every check passes. The sync is still broken.", { x: M, y: 3.86, w: 7.2,
    h: 0.44, isTextBox: true, margin: 0, fontSize: 24, color: INK, fontFace: "Cambria" });
  s.addText("“Galileo reachable. DB fine. Service running.” The checklist completes and has nothing left to say. The cause is often never found — only worked around.",
    { x: M, y: 4.38, w: 7.2, h: 0.9, isTextBox: true, margin: 0,
      fontSize: 14, color: MUTED, fontFace: "Calibri" });
  s.addText("DAYS", { x: 9.1, y: 3.64, w: 3.2, h: 0.95, isTextBox: true, margin: 0,
    fontSize: 54, color: ACCENT, fontFace: "Cambria" });
  s.addText("of engineer time per incident, across three teams — and the knowledge leaves with whoever solved it.",
    { x: 9.1, y: 4.66, w: 3.23, h: 0.9, isTextBox: true, margin: 0,
      fontSize: 12.5, color: MUTED, fontFace: "Calibri" });
  s.addNotes("45s. Seven consoles, seven manual checks. The painful part is not the time — " +
    "the checklist can complete and leave you with nothing. And whatever was learned " +
    "walks out of the door with the person who learned it.");
}

// ================================================== 3 WHAT YOU GET
{
  pres.addSection({ title: "Solution" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Solution" });
  eyebrow(s, "The solution");
  s.addText("One paste. Six answers, not one", { placeholder: "title" });
  s.addText("No consoles, no credentials, nothing installed on the systems being diagnosed.",
    { x: M, y: 1.7, w: 10.6, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const out = [
    ["01", "Root cause", "The failing layer, named — and the rule that decided it."],
    ["02", "Confidence", "High, Medium or Inconclusive, with the reason for the limit."],
    ["03", "Evidence", "Every observation, each tagged with the source it came from."],
    ["04", "Ruled out", "The other candidate causes it is not, and why each was excluded."],
    ["05", "Precedent", "Past incidents of the same shape, and whether the fix held."],
    ["06", "Fix & prevention", "The runbook step, what not to do, and how to stop it recurring."],
  ];
  out.forEach(([n, t, d], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * 3.87, y = 2.34 + row * 1.66;
    s.addShape(pres.ShapeType.rect, { x, y, w: 3.58, h: 1.42,
      fill: { color: TINT }, line: { width: 0 }, objectName: `out${i}` });
    s.addText(n, { x: x + 0.3, y: y + 0.22, w: 0.6, h: 0.24, isTextBox: true,
      margin: 0, fontSize: 10, color: ACCENT, fontFace: MONO });
    s.addText(t, { x: x + 0.3, y: y + 0.48, w: 2.98, h: 0.3, isTextBox: true,
      margin: 0, fontSize: 15, bold: true, color: INK, fontFace: "Calibri" });
    s.addText(d, { x: x + 0.3, y: y + 0.79, w: 2.98, h: 0.5, isTextBox: true,
      margin: 0, fontSize: 11.5, color: MUTED, fontFace: "Calibri" });
  });
  hr(s, 5.84);
  s.addText([
    { text: "Read-only by design. ", options: { bold: true, color: INK } },
    { text: "It never restarts anything and never writes to a system it is diagnosing — which is what clears risk review.",
      options: { color: MUTED } },
  ], { x: M, y: 6.04, w: 11.2, h: 0.56, isTextBox: true, margin: 0,
       fontSize: 14, fontFace: "Calibri" });
  s.addNotes("50s. Six outputs, not one. Numbers 4 and 5 are what change the response: what " +
    "it is NOT, and whether we have seen it before. Number 6 includes what not to do, " +
    "which is usually where the time is actually lost. And it is read-only — nothing to " +
    "argue about with risk review.");
}

// ================================================== 4 ARCHITECTURE + STACK
{
  pres.addSection({ title: "Architecture" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Architecture" });
  eyebrow(s, "How it works");
  s.addText("Evidence decides. The model explains", { placeholder: "title" });
  s.addText("Seven stages. Six establish what happened from the log; the last one turns that into language a tired engineer can read.",
    { x: M, y: 1.68, w: 11.2, h: 0.56, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const stages = [
    ["01", "Parse", "Serilog → lines", false],
    ["02", "Extract", "typed evidence", false],
    ["03", "Derive", "elapsed, rate", false],
    ["04", "Decide", "rules → cause", false],
    ["05", "Look up", "owner, runbook", false],
    ["06", "Score", "confidence", false],
    ["07", "Explain", "summarise & answer", true],
  ];
  const gap = 0.17, bw = (CW - gap * 6) / 7;
  stages.forEach(([n, t, d, ai], i) => {
    const x = M + i * (bw + gap);
    s.addShape(pres.ShapeType.rect, { x, y: 2.34, w: bw, h: 1.5,
      fill: { color: ai ? INK : TINT }, line: { width: 0 }, objectName: `st${i}` });
    s.addText(n, { x: x + 0.16, y: 2.52, w: bw - 0.32, h: 0.24, isTextBox: true,
      margin: 0, fontSize: 10, color: ai ? ACCENT : FAINT, fontFace: MONO });
    s.addText(t, { x: x + 0.16, y: 2.8, w: bw - 0.28, h: 0.3, isTextBox: true,
      margin: 0, fontSize: 13.5, bold: true, color: ai ? PAPER : INK, fontFace: "Calibri" });
    s.addText(d, { x: x + 0.16, y: 3.12, w: bw - 0.28, h: 0.56, isTextBox: true,
      margin: 0, fontSize: 10, color: ai ? "A8AEB5" : MUTED, fontFace: "Calibri" });
  });

  s.addText("The model summarises the finished result, rephrases it for the reader, and answers follow-up questions about it. Because the verdict is already established, the explanation can never drift away from the facts.",
    { x: M, y: 4.08, w: 11.0, h: 0.62, isTextBox: true, margin: 0,
      fontSize: 14.5, color: INK, fontFace: "Calibri" });

  hr(s, 4.92);
  s.addText("BUILT WITH", { x: M, y: 5.14, w: 3.0, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 9.5, bold: true, charSpacing: 1.6, color: FAINT, fontFace: "Calibri" });
  const stack = [
    ["Python 3.12", "engine"], ["FastAPI", "12 endpoints"],
    ["React", "single file, no build"], ["Gemini 3.5", "stage 07"],
    ["Knowledge graph", "70 nodes"], ["Vector search", "past incidents"],
  ];
  stack.forEach(([n, r], i) => {
    const x = M + i * 1.9;
    s.addText(n, { x, y: 5.48, w: 1.82, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 13, bold: true, color: INK, fontFace: "Calibri" });
    s.addText(r, { x, y: 5.76, w: 1.82, h: 0.46, isTextBox: true, margin: 0,
      fontSize: 10.5, color: MUTED, fontFace: "Calibri" });
  });
  s.addNotes("65s. Walk left to right. Six stages establish the facts from the log — parse, " +
    "extract, derive, decide, look up, score. Stage seven is the AI: it summarises the " +
    "result, rephrases it, and answers questions about it. The key point: the verdict " +
    "exists before the model is called, so the explanation always matches the evidence. " +
    "Stack along the bottom — keep this quick.");
}

// ================================================== 5 ASK THE DIAGNOSIS
{
  pres.addSection({ title: "Ask" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Ask" });
  eyebrow(s, "Ask the diagnosis");
  s.addText("Two modes, so nobody has to know the system first", { placeholder: "title" });
  s.addText("Anyone can interrogate the result — including an engineer who has never seen this application before.",
    { x: M, y: 1.7, w: 11.0, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  // PROJECT
  s.addShape(pres.ShapeType.rect, { x: M, y: 2.3, w: 5.5, h: 3.2,
    fill: { color: TINT }, line: { width: 0 }, objectName: "projCard" });
  s.addText("PROJECT  ·  GROUNDED", { x: M + 0.36, y: 2.56, w: 4.8, h: 0.24,
    isTextBox: true, margin: 0, fontSize: 10, bold: true, charSpacing: 1.8,
    color: ACCENT, fontFace: "Calibri" });
  s.addText("Answers only from this investigation, the topology graph and past incidents.",
    { x: M + 0.36, y: 2.86, w: 4.8, h: 0.5, isTextBox: true, margin: 0,
      fontSize: 13, color: INK, fontFace: "Calibri" });
  ["“Which team owns this?”", "“What does this application depend on?”",
   "“Have we seen this before, and did the fix hold?”"].forEach((q, i) => {
    s.addText(q, { x: M + 0.36, y: 3.42 + i * 0.32, w: 4.8, h: 0.3, isTextBox: true,
      margin: 0, fontSize: 12, color: MUTED, fontFace: "Calibri" });
  });
  hr(s, 4.46, M + 0.36, 4.8, "DEE0E3");
  s.addText("Relationships come from a knowledge graph; similar incidents from vector search over past write-ups. The model picks which lookup to run — the backend runs it, and every answer shows its source.",
    { x: M + 0.36, y: 4.6, w: 4.8, h: 0.78, isTextBox: true, margin: 0,
      fontSize: 11.5, color: MUTED, fontFace: "Calibri" });

  // GENERAL
  s.addShape(pres.ShapeType.rect, { x: 6.83, y: 2.3, w: 5.5, h: 3.2,
    fill: { color: TINT }, line: { width: 0 }, objectName: "genCard" });
  s.addText("GENERAL  ·  OPEN", { x: 7.19, y: 2.56, w: 4.8, h: 0.24,
    isTextBox: true, margin: 0, fontSize: 10, bold: true, charSpacing: 1.8,
    color: MUTED, fontFace: "Calibri" });
  s.addText("A full technical assistant for everything that is not about this incident.",
    { x: 7.19, y: 2.86, w: 4.8, h: 0.5, isTextBox: true, margin: 0,
      fontSize: 13, color: INK, fontFace: "Calibri" });
  ["“What is an HTTP 504?”", "“How do nginx proxy timeouts work?”",
   "“Show me the config to change it.”"].forEach((q, i) => {
    s.addText(q, { x: 7.19, y: 3.42 + i * 0.32, w: 4.8, h: 0.3, isTextBox: true,
      margin: 0, fontSize: 12, color: MUTED, fontFace: "Calibri" });
  });
  hr(s, 4.46, 7.19, 4.8, "DEE0E3");
  s.addText("Full answers with tables and code. It will not claim anything about the current incident — if you ask, it says so and points you back to Project mode.",
    { x: 7.19, y: 4.6, w: 4.8, h: 0.78, isTextBox: true, margin: 0,
      fontSize: 11.5, color: MUTED, fontFace: "Calibri" });

  hr(s, 5.78);
  s.addText([
    { text: "A new joiner can ask the system instead of asking a colleague. ", options: { bold: true, color: INK } },
    { text: "The dependency chain comes out of the topology graph, so the answer is the real one — not a model's recollection of it.",
      options: { color: MUTED } },
  ], { x: M, y: 6.0, w: 11.0, h: 0.6, isTextBox: true, margin: 0,
       fontSize: 14, fontFace: "Calibri" });
  s.addNotes("75s. This is a feature judges will not have seen elsewhere. Two modes. " +
    "Project mode answers only from verified project data — relationships from a " +
    "knowledge graph, past incidents from vector search. The model chooses which lookup " +
    "to run; the backend runs it. General mode is an ordinary technical assistant. " +
    "The pitch line is the last one: a new joiner can ask the system instead of " +
    "interrupting whoever knows the application chain.");
}

// ================================================== 6 DIFFERENTIATOR
{
  pres.addSection({ title: "Differentiator" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Differentiator" });
  eyebrow(s, "Why this is different");
  s.addText("Everyone can call an LLM. That isn’t the hard part", { placeholder: "title" });

  s.addText("TYPICAL LOG-ANALYSIS TOOL", { x: M, y: 1.76, w: 4.9, h: 0.24,
    isTextBox: true, margin: 0, fontSize: 9.5, bold: true, charSpacing: 1.6,
    color: FAINT, fontFace: "Calibri" });
  s.addText("THIS", { x: 6.5, y: 1.76, w: 5.8, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 9.5, bold: true, charSpacing: 1.6, color: ACCENT, fontFace: "Calibri" });
  hr(s, 2.04, M, 4.9, "E8EAEC");
  hr(s, 2.04, 6.5, 5.83, ACCENT, 0.014);

  const rows = [
    ["Asks the model what broke", "Evidence decides; the model is never asked",
     "Hallucination cannot reach the diagnosis"],
    ["Always answers, even when wrong", "Returns “Inconclusive” and shows its working",
     "Silence beats a confident wrong answer at 2am"],
    ["Confidence is a number the model invented", "Confidence is capped by what we can actually see",
     "3 of 7 sources connected means it cannot claim High"],
    ["Hardcoded to one system", "Four JSON files: topology, rules, runbooks, incident history",
     "Another team adopts it without writing any code"],
    ["Breaks when the API is down", "Runs with the AI switched off entirely",
     "264 tests pass with no key and no network"],
  ];
  rows.forEach(([a, b, c], i) => {
    const y = 2.26 + i * 0.84;
    s.addText(a, { x: M, y: y + 0.04, w: 4.9, h: 0.5, isTextBox: true, margin: 0,
      fontSize: 13, color: FAINT, fontFace: "Calibri" });
    s.addText(b, { x: 6.5, y, w: 5.83, h: 0.34, isTextBox: true, margin: 0,
      fontSize: 13.5, bold: true, color: INK, fontFace: "Calibri" });
    s.addText(c, { x: 6.5, y: y + 0.34, w: 5.83, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 11.5, color: ACCENT, fontFace: "Calibri" });
  });

  hr(s, 6.58);
  s.addText("The reliability is structural, not a prompt we tuned — and the portability is config, not a rewrite.",
    { x: M, y: 6.78, w: 11.0, h: 0.42, isTextBox: true, margin: 0,
      fontSize: 14.5, italic: true, color: INK, fontFace: "Cambria" });
  s.addNotes("90s — slow down, this is the slide the pitch turns on. Read the right-hand " +
    "column aloud. Row four is the portability USP: all the domain knowledge lives in " +
    "four JSON files — the topology, the rules, the runbooks and the incident history. " +
    "Another team points it at their own system by editing those, with no code change. " +
    "Finish on the closing line.");
}

// ================================================== 7 BEYOND THE FIX
{
  pres.addSection({ title: "Close" });
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Close" });
  s.addText("BEYOND THE FIX", { x: M, y: 0.8, w: CW, h: 0.28, isTextBox: true,
    margin: 0, fontSize: 10.5, bold: true, charSpacing: 2.8, color: ACCENT,
    fontFace: "Calibri" });
  s.addText("Every incident makes the next one cheaper", { x: M, y: 1.2, w: 11.0,
    h: 0.68, isTextBox: true, margin: 0, fontSize: 33, color: PAPER, fontFace: "Cambria" });

  const cards = [
    ["STOP IT RECURRING",
     "Actions across code, config, monitoring and process — plus the safe batch size, calculated from the throughput measured in the log, not typed in by hand."],
    ["WHAT NOT TO DO",
     "An explicit do-not list. “Do not raise the client timeout” — because the client was never what cut the connection. This is where hours normally go."],
    ["WHY IT WAS HARD TO FIND",
     "It scores our own logging: 5 of 10 practices. We never record how long a job takes, which is why a sync degrading for weeks stayed invisible."],
  ];
  cards.forEach(([h, b], i) => {
    const x = M + i * 3.87;
    s.addText(h, { x, y: 2.2, w: 3.5, h: 0.26, isTextBox: true, margin: 0,
      fontSize: 9.5, bold: true, charSpacing: 1.6, color: ACCENT, fontFace: "Calibri" });
    hr(s, 2.54, x, 3.5, "34393F");
    s.addText(b, { x, y: 2.68, w: 3.5, h: 1.5, isTextBox: true, margin: 0,
      fontSize: 12.5, color: "A8AEB5", fontFace: "Calibri" });
  });

  hr(s, 4.46, M, CW, "34393F");
  const stats = [["264", "tests passing, offline"], ["8", "failure classes"],
                 ["4", "config files"], ["2 s", "to an answer"]];
  stats.forEach(([n, l], i) => {
    const x = M + i * 2.87;
    s.addText(n, { x, y: 4.72, w: 2.7, h: 0.8, isTextBox: true, margin: 0,
      fontSize: 42, color: PAPER, fontFace: MONO });
    s.addText(l, { x, y: 5.54, w: 2.7, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 12, color: "787F87", fontFace: "Calibri" });
  });

  s.addText("Next: swap Gemini for the bank’s approved Azure OpenAI endpoint — one file changes.",
    { x: M, y: 6.06, w: 11.0, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 12, color: "6A7179", fontFace: "Calibri" });
  s.addText("Evidence decides what happened. The model explains it.", { x: M, y: 6.46,
    w: 8.0, h: 0.42, isTextBox: true, margin: 0, fontSize: 19, italic: true,
    color: PAPER, fontFace: "Cambria" });
  s.addText("TEAM POTENTIAL", { x: W - M - 3.0, y: 6.56, w: 3.0, h: 0.28,
    isTextBox: true, margin: 0, fontSize: 11.5, bold: true, charSpacing: 2.6,
    color: ACCENT, fontFace: "Calibri", align: "right" });
  s.addNotes("65s, then stop and take questions. Three things beyond the fix: how to stop " +
    "it recurring with a calculated batch size, an explicit do-not list, and a score on " +
    "our own logging. That last one is the honest one — we score 5 out of 10, and the " +
    "biggest gap explains why this was invisible for weeks. Then the numbers: 264 tests " +
    "passing offline says this is real, two seconds against days is the business case. " +
    "Close on the line and stop talking.");
}

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
  console.log("wrote " + OUT);
});
