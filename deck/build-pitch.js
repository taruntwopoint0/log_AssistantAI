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
      ACCENT = "B4472E", RULE = "E2E4E7", PAPER = "FFFFFF";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Team Potential";
pres.company = "Team Potential";
pres.title = "AI Investigation Assistant";

const W = 13.333, H = 7.5, M = 1.0;
const CW = W - M * 2;                 // 11.333

pres.defineSlideMaster({ title: "DARK", background: { color: INK }, objects: [] });
pres.defineSlideMaster({
  title: "LIGHT",
  background: { color: PAPER },
  objects: [
    { placeholder: { options: {
        name: "title", type: "title", x: M, y: 0.74, w: CW, h: 0.82,
        fontSize: 34, color: INK, fontFace: "Cambria", align: "left",
        valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: W - M - 0.35, y: H - 0.58, w: 0.35, h: 0.26,
                 fontSize: 9.5, color: "C7CACE", align: "right", fontFace: "Calibri" },
});

const eyebrow = (s, t, c = ACCENT) => s.addText(t.toUpperCase(), {
  x: M, y: 0.42, w: CW, h: 0.24, isTextBox: true, margin: 0,
  fontSize: 10, bold: true, charSpacing: 2.4, color: c, fontFace: "Calibri" });

const hr = (s, y, x = M, w = CW, c = RULE, h = 0.01) =>
  s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: c }, line: { width: 0 } });

// ======================================================= 1 OVERVIEW
{
  pres.addSection({ title: "Overview" });
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Overview" });

  s.addText("TEAM POTENTIAL", { x: M, y: 1.6, w: CW, h: 0.28, isTextBox: true,
    margin: 0, fontSize: 11.5, bold: true, charSpacing: 3.2, color: ACCENT,
    fontFace: "Calibri" });

  s.addText("AI Investigation Assistant", { x: M, y: 2.05, w: CW, h: 0.95,
    isTextBox: true, margin: 0, fontSize: 52, color: PAPER, fontFace: "Cambria" });

  s.addText("Paste a failing log. Get the root cause, the evidence behind it, and the fix.",
    { x: M, y: 3.08, w: 9.6, h: 0.42, isTextBox: true, margin: 0,
      fontSize: 17.5, color: "A8AEB5", fontFace: "Calibri" });

  hr(s, 4.05, M, 2.6, "363B41");

  s.addText([
    { text: "The AI never decides what broke.", options: { color: PAPER, bold: true } },
    { text: "  That is the entire point.", options: { color: ACCENT } },
  ], { x: M, y: 4.32, w: 10.5, h: 0.42, isTextBox: true, margin: 0,
       fontSize: 20, fontFace: "Cambria" });

  s.addText("LEAP Young Innovators 2026   ·   Theme 3, Log Analysis   ·   Société Générale",
    { x: M, y: 6.3, w: CW, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 12, color: "6A7179", fontFace: "Calibri" });

  s.addNotes(
    "30 seconds. We are Team Potential. This takes a failing log and returns the root " +
    "cause with the evidence. The line at the bottom is what separates us from every " +
    "other log-analysis project here: the language model is never asked what broke. " +
    "I will show you why that matters."
  );
}

// ======================================================= 2 PROBLEM
{
  pres.addSection({ title: "Problem" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Problem" });
  eyebrow(s, "The problem");
  s.addText("Seven consoles, and often still no answer", { placeholder: "title" });

  s.addText("When the supplier sync fails, an engineer checks seven systems by hand. Each one is a different tool.",
    { x: M, y: 1.7, w: 10.6, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const checks = ["Windows Service", "Aldavar DB", "Database views", "Galileo",
                  "ALD SAT endpoints", "Network", "Application logs"];
  checks.forEach((c, i) => {
    const x = M + i * 1.62;
    s.addText(String(i + 1).padStart(2, "0"), { x, y: 2.5, w: 1.45, h: 0.24,
      isTextBox: true, margin: 0, fontSize: 10, color: FAINT, fontFace: MONO });
    s.addText(c, { x, y: 2.76, w: 1.5, h: 0.6, isTextBox: true, margin: 0,
      fontSize: 12.5, color: INK, fontFace: "Calibri" });
  });
  hr(s, 3.5);

  s.addText("Every check passes. The sync is still broken.", {
    x: M, y: 3.86, w: 7.2, h: 0.44, isTextBox: true, margin: 0,
    fontSize: 24, color: INK, fontFace: "Cambria" });
  s.addText("“Galileo reachable. DB fine. Service running.” The checklist completes and has nothing left to say. The cause is often never found — only worked around.",
    { x: M, y: 4.38, w: 7.2, h: 0.9, isTextBox: true, margin: 0,
      fontSize: 14, color: MUTED, fontFace: "Calibri" });

  s.addText("DAYS", { x: 9.1, y: 3.64, w: 3.2, h: 0.95, isTextBox: true, margin: 0,
    fontSize: 54, color: ACCENT, fontFace: "Cambria" });
  s.addText("of engineer time per incident, across three teams, for a fault that was visible in the log the whole time.",
    { x: 9.1, y: 4.66, w: 3.23, h: 0.9, isTextBox: true, margin: 0,
      fontSize: 12.5, color: MUTED, fontFace: "Calibri" });

  s.addNotes(
    "45 seconds. Seven consoles, seven manual checks. The painful part is not the time. " +
    "It is that the checklist can complete and leave you with nothing — every source " +
    "reports healthy and the sync is still down."
  );
}

// ======================================================= 3 THE INSIGHT
{
  pres.addSection({ title: "Insight" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Insight" });
  eyebrow(s, "What we found");
  s.addText("The answer was in the log the whole time", { placeholder: "title" });

  s.addText("18 August 2026. Small batches succeeded all day. Every large batch died at the same second.",
    { x: M, y: 1.7, w: 10.6, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const head = ["RECORDS", "OUTCOME", "ELAPSED"];
  const data = [["2", "200 OK", "1 s"], ["39", "200 OK", "7 s"],
                ["539", "FAILED", "62 s"], ["545", "FAILED", "61 s"],
                ["537", "FAILED", "60 s"]];
  head.forEach((h, i) => s.addText(h, {
    x: M + i * 1.55, y: 2.46, w: 1.5, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 9.5, bold: true, charSpacing: 1.4, color: FAINT, fontFace: "Calibri" }));
  hr(s, 2.74, M, 4.55);
  data.forEach((r, ri) => r.forEach((cell, ci) => {
    const bad = r[1] === "FAILED";
    s.addText(cell, {
      x: M + ci * 1.55, y: 2.86 + ri * 0.38, w: 1.5, h: 0.3, isTextBox: true,
      margin: 0, fontSize: 13, fontFace: MONO,
      color: bad && ci > 0 ? ACCENT : (bad ? INK : FAINT) });
  }));

  // the arithmetic
  const ax = 6.3;
  s.addText("THE ARITHMETIC NOBODY DID", { x: ax, y: 2.46, w: 6.0, h: 0.24,
    isTextBox: true, margin: 0, fontSize: 9.5, bold: true, charSpacing: 1.4,
    color: FAINT, fontFace: "Calibri" });
  hr(s, 2.74, ax, 6.03);
  const maths = [
    ["39 records in 7 s", "0.179 s per record"],
    ["539 × 0.179", "97 s of work needed"],
    ["cut after", "60 s"],
  ];
  maths.forEach(([l, r], i) => {
    const y = 2.9 + i * 0.44;
    s.addText(l, { x: ax, y, w: 2.9, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 13.5, color: MUTED, fontFace: MONO });
    s.addText(r, { x: ax + 2.95, y, w: 3.1, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 13.5, color: i === 2 ? ACCENT : INK, bold: i === 2, fontFace: MONO });
  });

  hr(s, 4.82);
  s.addText("A round 60-second ceiling, below the time the work actually takes, is a configured timeout on something in between.",
    { x: M, y: 5.02, w: 11.0, h: 0.72, isTextBox: true, margin: 0,
      fontSize: 19, color: INK, fontFace: "Cambria" });
  s.addText([
    { text: "Galileo was never down. ", options: { bold: true, color: INK } },
    { text: "No single console could show this — the proof is arithmetic across lines, and that is exactly what a machine is good at and a human on call at 2am is not.",
      options: { color: MUTED } },
  ], { x: M, y: 5.80, w: 11.0, h: 0.6, isTextBox: true, margin: 0,
       fontSize: 14, fontFace: "Calibri" });

  s.addNotes(
    "75 seconds, and this is the credibility slide. Look at the pattern: it is size, not " +
    "time of day. 39 records took 7 seconds, so 539 needs about 97. It was cut at 60. " +
    "A round number below the work's real duration means a configured timeout upstream. " +
    "Galileo was never down — it answered small batches all day. Three teams missed this " +
    "for days because no console shows it. The tool finds it in two seconds."
  );
}

// ======================================================= 4 ARCHITECTURE
{
  pres.addSection({ title: "Architecture" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Architecture" });
  eyebrow(s, "How it works");
  s.addText("Seven stages. The AI is only the last one", { placeholder: "title" });

  const stages = [
    ["01", "Parse", "Serilog → lines", false],
    ["02", "Extract", "typed evidence", false],
    ["03", "Derive", "elapsed, rate", false],
    ["04", "Decide", "rules → cause", false],
    ["05", "Look up", "owner, runbook", false],
    ["06", "Score", "confidence", false],
    ["07", "Write", "model phrases it", true],
  ];
  const gap = 0.17, bw = (CW - gap * 6) / 7;
  stages.forEach(([n, t, d, ai], i) => {
    const x = M + i * (bw + gap);
    s.addShape(pres.ShapeType.rect, { x, y: 2.3, w: bw, h: 1.5,
      fill: { color: ai ? INK : "F5F5F3" }, line: { width: 0 },
      objectName: `st${i}` });
    s.addText(n, { x: x + 0.16, y: 2.48, w: bw - 0.32, h: 0.24, isTextBox: true,
      margin: 0, fontSize: 10, color: ai ? ACCENT : FAINT, fontFace: MONO });
    s.addText(t, { x: x + 0.16, y: 2.76, w: bw - 0.28, h: 0.3, isTextBox: true,
      margin: 0, fontSize: 13.5, bold: true, color: ai ? PAPER : INK,
      fontFace: "Calibri" });
    s.addText(d, { x: x + 0.16, y: 3.08, w: bw - 0.28, h: 0.56, isTextBox: true,
      margin: 0, fontSize: 10, color: ai ? "A8AEB5" : MUTED, fontFace: "Calibri" });
  });

  s.addText("STAGES 01–06   ·   NO AI, NO NETWORK, NO CREDENTIALS", {
    x: M, y: 3.98, w: 9.5, h: 0.26, isTextBox: true, margin: 0,
    fontSize: 10, bold: true, charSpacing: 1.6, color: MUTED, fontFace: "Calibri" });

  hr(s, 4.52);
  s.addText("Switch stage 07 off and every answer is identical — only the wording is plainer.",
    { x: M, y: 4.78, w: 11.0, h: 0.42, isTextBox: true, margin: 0,
      fontSize: 19, color: INK, fontFace: "Cambria" });
  s.addText("The decision has already been made by the time the model is called. It receives a finished conclusion and turns it into a sentence. It cannot change the cause, the confidence, or the evidence — because it is never shown the question.",
    { x: M, y: 5.3, w: 11.0, h: 0.7, isTextBox: true, margin: 0,
      fontSize: 14, color: MUTED, fontFace: "Calibri" });

  s.addNotes(
    "60 seconds. Six deterministic stages, then one AI stage. Stages 1 to 6 are plain " +
    "Python — regex, dictionary lookups, arithmetic. No network, no credentials, no model. " +
    "By the time the model is called, the answer already exists. It only writes the " +
    "paragraph. That is why hallucination cannot reach the diagnosis."
  );
}

// ======================================================= 5 TECH STACK
{
  pres.addSection({ title: "Stack" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Stack" });
  eyebrow(s, "Tech stack");
  s.addText("Chosen so the decision stays auditable", { placeholder: "title" });

  const items = [
    ["Python 3.12", "Rules, parser, scorer", "The whole decision path. Standard library only — no framework between the evidence and the answer."],
    ["FastAPI", "12 REST endpoints", "Thin layer. Serves the dashboard and exposes the engine; holds no logic of its own."],
    ["React", "Single file, CDN, no build", "The dashboard runs from one HTML file, so there is nothing to compile or deploy."],
    ["Gemini 3.5", "Stage 07 only", "Writes the summary and answers questions. Swappable for Azure OpenAI by editing one file."],
    ["Knowledge graph", "70 nodes, 121 edges", "Built in-process from the config. Answers “who owns this?” by traversal, not by asking a model."],
    ["Vector search", "Embedded signatures", "Finds past incidents described in different words. Never embeds a raw stack trace."],
  ];
  items.forEach(([name, role, why], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 5.82, y = 2.0 + row * 1.52;
    s.addText(name, { x, y, w: 3.0, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 15.5, bold: true, color: INK, fontFace: "Calibri" });
    s.addText(role, { x: x + 3.05, y: y + 0.05, w: 2.4, h: 0.26, isTextBox: true,
      margin: 0, fontSize: 10.5, color: i === 3 ? ACCENT : FAINT, fontFace: MONO,
      align: "right" });
    s.addText(why, { x, y: y + 0.34, w: 5.45, h: 0.72, isTextBox: true, margin: 0,
      fontSize: 12.5, color: MUTED, fontFace: "Calibri" });
    hr(s, y + 1.16, x, 5.45, "EDEEF0");
  });

  s.addText("Exactly one of these six can reach the internet, and it runs after the answer exists.",
    { x: M, y: 6.42, w: 11.0, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 14.5, italic: true, color: ACCENT, fontFace: "Cambria" });

  s.addNotes(
    "45 seconds. Keep this quick. The point of the slide is the last line: one component " +
    "touches the internet, and it runs after the decision is made. The graph and the " +
    "vector search are real but they only enrich — they never decide."
  );
}

// ======================================================= 6 THE ALPHA
{
  pres.addSection({ title: "Differentiator" });
  const s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Differentiator" });
  eyebrow(s, "Why this is different");
  s.addText("Everyone can call an LLM. That isn’t the hard part", { placeholder: "title" });

  s.addText("TYPICAL LOG-ANALYSIS TOOL", { x: M, y: 1.78, w: 4.9, h: 0.24,
    isTextBox: true, margin: 0, fontSize: 9.5, bold: true, charSpacing: 1.6,
    color: FAINT, fontFace: "Calibri" });
  s.addText("THIS", { x: 6.5, y: 1.78, w: 5.8, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 9.5, bold: true, charSpacing: 1.6, color: ACCENT, fontFace: "Calibri" });
  hr(s, 2.06, M, 4.9, "E8EAEC");
  hr(s, 2.06, 6.5, 5.83, ACCENT, 0.014);

  const rows = [
    ["Asks the model what broke", "The model is never asked. Rules decide",
     "Hallucination cannot reach the diagnosis"],
    ["Always answers, even when wrong", "Returns “Inconclusive” and shows its working",
     "Silence beats a confident wrong answer at 2am"],
    ["Confidence is a number the model invented", "Confidence is capped by what we can actually see",
     "3 of 7 sources connected means it cannot claim High"],
    ["Sends your logs to a third party", "Hostnames and IDs are tokenised before any prompt leaves",
     "The raw log never leaves the machine"],
    ["Breaks when the API is down", "Runs with the AI switched off entirely",
     "264 tests pass with no key and no network"],
  ];
  rows.forEach(([a, b, c], i) => {
    const y = 2.28 + i * 0.84;
    s.addText(a, { x: M, y: y + 0.04, w: 4.9, h: 0.5, isTextBox: true, margin: 0,
      fontSize: 13, color: FAINT, fontFace: "Calibri", valign: "top" });
    s.addText(b, { x: 6.5, y, w: 5.83, h: 0.34, isTextBox: true, margin: 0,
      fontSize: 13.5, bold: true, color: INK, fontFace: "Calibri" });
    s.addText(c, { x: 6.5, y: 0.34 + y, w: 5.83, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 11.5, color: ACCENT, fontFace: "Calibri" });
  });

  hr(s, 6.6);
  s.addText("The reliability is structural, not a prompt we tuned. That is what makes it deployable in a bank.",
    { x: M, y: 6.8, w: 11.0, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 14.5, italic: true, color: INK, fontFace: "Cambria" });

  s.addNotes(
    "90 seconds — this is the slide that wins or loses it. Slow down here. Everyone in " +
    "this room can call an LLM over a log file. The hard part is what happens when the " +
    "model is wrong, and the honest answer for most tools is: nothing, it just tells you " +
    "something false with confidence. Ours cannot, because the model is never asked. " +
    "Read the right-hand column out loud. Finish on the last line: structural, not a prompt."
  );
}

// ======================================================= 7 PROOF + CLOSE
{
  pres.addSection({ title: "Close" });
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Close" });

  s.addText("WHAT IS ACTUALLY BUILT", { x: M, y: 0.86, w: CW, h: 0.28,
    isTextBox: true, margin: 0, fontSize: 10.5, bold: true, charSpacing: 2.8,
    color: ACCENT, fontFace: "Calibri" });
  s.addText("Working today, not a prototype", { x: M, y: 1.28, w: 10.6, h: 0.68,
    isTextBox: true, margin: 0, fontSize: 34, color: PAPER, fontFace: "Cambria" });

  const stats = [
    ["264", "tests passing", "Offline. No API key needed."],
    ["8", "failure classes", "Each one a rule in a JSON file."],
    ["4", "config files", "Another team adapts it without writing code."],
    ["2 s", "to an answer", "Against days of manual checking."],
  ];
  stats.forEach(([n, l, d], i) => {
    const x = M + i * 2.87;
    s.addText(n, { x, y: 2.46, w: 2.6, h: 0.86, isTextBox: true, margin: 0,
      fontSize: 48, color: PAPER, fontFace: MONO });
    s.addText(l, { x, y: 3.34, w: 2.6, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 13, bold: true, color: "C7CACE", fontFace: "Calibri" });
    s.addText(d, { x, y: 3.64, w: 2.6, h: 0.56, isTextBox: true, margin: 0,
      fontSize: 11, color: "787F87", fontFace: "Calibri" });
  });

  hr(s, 4.55, M, CW, "34393F");

  s.addText("BEYOND THE FIX", { x: M, y: 4.8, w: 5.4, h: 0.24, isTextBox: true,
    margin: 0, fontSize: 9.5, bold: true, charSpacing: 1.6, color: ACCENT,
    fontFace: "Calibri" });
  s.addText("It also says how to stop the failure recurring, and scores our own logging — we score 5 of 10, and the gaps explain why this took days to find.",
    { x: M, y: 5.08, w: 5.4, h: 0.86, isTextBox: true, margin: 0,
      fontSize: 12.5, color: "A8AEB5", fontFace: "Calibri" });

  s.addText("NEXT", { x: 6.9, y: 4.8, w: 5.43, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 9.5, bold: true, charSpacing: 1.6, color: ACCENT, fontFace: "Calibri" });
  s.addText("Swap Gemini for the bank's approved Azure OpenAI endpoint — one file changes. Port the engine to .NET to sit beside the worker it watches.",
    { x: 6.9, y: 5.08, w: 5.43, h: 0.86, isTextBox: true, margin: 0,
      fontSize: 12.5, color: "A8AEB5", fontFace: "Calibri" });

  s.addText("Code decides what happened. The model only explains it.", {
    x: M, y: 6.34, w: 8.0, h: 0.42, isTextBox: true, margin: 0,
    fontSize: 20, italic: true, color: PAPER, fontFace: "Cambria" });
  s.addText("TEAM POTENTIAL", { x: W - M - 3.0, y: 6.44, w: 3.0, h: 0.28,
    isTextBox: true, margin: 0, fontSize: 11.5, bold: true, charSpacing: 2.6,
    color: ACCENT, fontFace: "Calibri", align: "right" });

  s.addNotes(
    "60 seconds, then stop and invite questions. Lead with 264 tests passing offline — " +
    "that is the line that says this is real. Two seconds against days is the business " +
    "case. Mention the roadmap briefly so they know we know what production needs. " +
    "Close on the one line and stop talking."
  );
}

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
  console.log("wrote " + OUT);
});
