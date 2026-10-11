const pptxgen = require("pptxgenjs");
const path = require("path");
const { applyTheme } = require(path.join(
  "C:/Users/Tarun S/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin",
  "c8b42d6b-e842-4a88-8e8a-c218bdce7852/8edae868-47db-4e1a-aa54-d65681e832b4/skills/pptx",
  "scripts/apply_theme.js"
));

const OUT = process.argv[2];

// Charcoal dominant, one sharp terracotta accent for the failure/cut.
// Green appears exactly twice, for "verified". Nothing else is coloured.
const THEME = {
  name: "Potential Charcoal",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "15181C",   // ink
    lt1: "FFFFFF",
    dk2: "6E7680",   // muted
    lt2: "F3F3F1",   // tint
    accent1: "B4472E", // terracotta — the cut
    accent2: "2E6A4F", // deep green — verified
    accent3: "15181C",
    accent4: "6E7680",
    accent5: "C9CCD1",
    accent6: "F3F3F1",
    hlink: "B4472E",
    folHlink: "6E7680",
  },
};

const MONO = "Courier New";        // motif: every machine-derived value
const INK = "15181C", MUTED = "6E7680", ACCENT = "B4472E",
      GREEN = "2E6A4F", RULE = "DCDEE2", TINT = "F3F3F1", PAPER = "FFFFFF";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";       // 13.333 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Team Potential";
pres.company = "Team Potential";
pres.title = "AI Investigation Assistant";

const W = 13.333, H = 7.5, M = 0.9;        // margin
const COLW = W - M * 2;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "DARK",
  background: { color: INK },
  objects: [],
});

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: PAPER },
  objects: [
    { placeholder: {
        options: { name: "title", type: "title", x: M, y: 0.62, w: COLW, h: 0.9,
                   fontSize: 38, bold: false, color: INK, fontFace: "Cambria",
                   align: "left", valign: "middle", margin: 0 },
        text: "" } },
  ],
  slideNumber: { x: W - M - 0.4, y: H - 0.62, w: 0.4, h: 0.3,
                 fontSize: 10, color: "C9CCD1", align: "right", fontFace: "Calibri" },
});

// ---------------------------------------------------------------- helpers
const txt = (s, o) => s.addText.bind(s);

function kicker(slide, text, color = MUTED) {
  slide.addText(text.toUpperCase(), {
    x: M, y: 0.3, w: COLW, h: 0.26, isTextBox: true, margin: 0,
    fontSize: 10.5, bold: true, charSpacing: 2.2, color, fontFace: "Calibri",
  });
}

function rule(slide, y, x = M, w = COLW, color = RULE) {
  slide.addShape(pres.ShapeType.rect, {
    x, y, w, h: 0.012, fill: { color }, line: { color, width: 0 },
  });
}

// ================================================================ 1. TITLE
{
  const s = (pres.addSection({ title: "Open" }), pres.addSlide({ masterName: "DARK", sectionTitle: "Open" }));

  s.addText("TEAM POTENTIAL", {
    x: M, y: 1.75, w: COLW, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 12, bold: true, charSpacing: 3.4, color: ACCENT, fontFace: "Calibri",
  });

  s.addText("AI Investigation Assistant", {
    x: M, y: 2.25, w: COLW, h: 1.0, isTextBox: true, margin: 0,
    fontSize: 54, color: PAPER, fontFace: "Cambria",
  });

  s.addText("Root cause from a pasted log, decided by code — not guessed by a model.", {
    x: M, y: 3.35, w: 8.6, h: 0.5, isTextBox: true, margin: 0,
    fontSize: 17, color: "A9AEB6", fontFace: "Calibri",
  });

  s.addShape(pres.ShapeType.rect, {
    x: M, y: 4.35, w: 3.0, h: 0.012, fill: { color: "3A3F46" }, line: { width: 0 },
  });

  s.addText([
    { text: "LEAP Young Innovators 2026", options: { bold: true, color: "C9CCD1" } },
    { text: "   ·   Theme 3, Log Analysis", options: { color: "6E7680" } },
  ], {
    x: M, y: 4.62, w: COLW, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 12.5, fontFace: "Calibri",
  });

  s.addText("BulkSuppliers supplier sync", {
    x: M, y: 4.95, w: COLW, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 12.5, color: "6E7680", fontFace: "Calibri",
  });

  s.addNotes(
    "We are Team Potential. The tool is an AI Investigation Assistant for log triage. " +
    "The one line that matters: code decides the root cause, the model only writes it up. " +
    "Everything in this deck follows from that choice."
  );
}

// ================================================================ 2. PROBLEM
{
  const s = (pres.addSection({ title: "Problem" }), pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" }));
  kicker(s, "The problem");
  s.addText("Seven consoles, and still no answer", { placeholder: "title" });

  s.addText(
    "An alert fires on the sync. Someone opens seven different tools and checks each by hand.",
    { x: M, y: 1.62, w: 9.9, h: 0.44, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const checks = [
    "Windows Service health", "Aldavar DB connectivity", "Database views",
    "Galileo availability", "ALD SAT endpoints", "Network connectivity",
    "Application logs",
  ];
  checks.forEach((c, i) => {
    const col = i < 4 ? 0 : 1;
    const row = i < 4 ? i : i - 4;
    const x = M + col * 3.55;
    const y = 2.35 + row * 0.52;
    s.addShape(pres.ShapeType.ellipse, {
      x, y: y + 0.085, w: 0.13, h: 0.13,
      fill: { color: "D8DBDF" }, line: { width: 0 }, objectName: `dot${i}`,
    });
    s.addText(c, { x: x + 0.3, y, w: 3.1, h: 0.34, isTextBox: true, margin: 0,
                   fontSize: 14, color: INK, fontFace: "Calibri", valign: "middle" });
  });

  // the dead end
  s.addShape(pres.ShapeType.rect, {
    x: 8.0, y: 2.2, w: COLW - 7.1, h: 2.5, fill: { color: TINT }, line: { width: 0 },
    objectName: "deadEndCard",
  });
  s.addText("WHERE IT ENDS", {
    x: 8.42, y: 2.52, w: 3.7, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 10, bold: true, charSpacing: 2, color: ACCENT, fontFace: "Calibri",
  });
  s.addText("“Galileo reachable. DB fine. Service running.”", {
    x: 8.42, y: 2.88, w: 3.7, h: 0.72, isTextBox: true, margin: 0,
    fontSize: 17, italic: true, color: INK, fontFace: "Cambria",
  });
  s.addText("Every check passes. The sync is still broken. The checklist has nothing left to say.",
    { x: 8.42, y: 3.68, w: 3.7, h: 0.85, isTextBox: true, margin: 0,
      fontSize: 13, color: MUTED, fontFace: "Calibri" });

  rule(s, 5.28);
  s.addText([
    { text: "Days of engineer time per incident", options: { color: INK, bold: true } },
    { text: "   —   and the cause is often never found, only worked around.",
      options: { color: MUTED } },
  ], { x: M, y: 5.5, w: COLW, h: 0.4, isTextBox: true, margin: 0,
       fontSize: 14, fontFace: "Calibri" });

  s.addNotes(
    "Today this is seven manual checks across seven consoles. The painful part is not the " +
    "time — it is that the checklist can complete and still leave you with nothing. " +
    "Every source reports healthy and the sync is still down."
  );
}

// ================================================================ 3. THE CASE
{
  const s = (pres.addSection({ title: "Evidence" }), pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" }));
  kicker(s, "The case we built it on");
  s.addText("18 August 2026", { placeholder: "title" });

  s.addText("Small batches succeeded all day. Every large batch died at the same moment.",
    { x: M, y: 1.62, w: 9.9, h: 0.44, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const rows = [
    [{ text: "TIME", options: { bold: true, color: MUTED, fontSize: 10, charSpacing: 1.4 } },
     { text: "RECORDS", options: { bold: true, color: MUTED, fontSize: 10, charSpacing: 1.4 } },
     { text: "OUTCOME", options: { bold: true, color: MUTED, fontSize: 10, charSpacing: 1.4 } },
     { text: "ELAPSED", options: { bold: true, color: MUTED, fontSize: 10, charSpacing: 1.4 } }],
    ...[["08:46", "2", "200 OK", "1 s"],
        ["11:03", "39", "200 OK", "7 s"],
        ["11:20", "539", "FAILED", "62 s"],
        ["11:21", "545", "FAILED", "61 s"],
        ["11:23", "537", "FAILED", "60 s"]
    ].map((r) => {
      const bad = r[2] === "FAILED";
      return r.map((cell, i) => ({
        text: cell,
        options: {
          fontFace: MONO, fontSize: 12.5,
          color: bad && (i === 2 || i === 3) ? ACCENT : (bad ? INK : MUTED),
          bold: bad && i === 3,
        },
      }));
    }),
  ];

  s.addTable(rows, {
    x: M, y: 2.25, w: 5.5, colW: [1.2, 1.4, 1.5, 1.4],
    rowH: 0.34, valign: "middle",
    border: [{ type: "none" }, { type: "none" },
             { type: "solid", color: "ECEDEF", pt: 1 }, { type: "none" }],
    margin: [2, 6, 2, 0], autoPage: false,
  });

  // the arithmetic
  s.addShape(pres.ShapeType.rect, {
    x: 7.05, y: 2.1, w: COLW - 6.15, h: 2.95, fill: { color: TINT },
    line: { width: 0 }, objectName: "mathCard",
  });
  s.addText("THE ARITHMETIC NOBODY DID", {
    x: 7.47, y: 2.42, w: 4.6, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 10, bold: true, charSpacing: 2, color: ACCENT, fontFace: "Calibri",
  });
  s.addText([
    { text: "39 records in 7 s", options: { fontFace: MONO, color: INK } },
    { text: "  =  0.179 s per record", options: { fontFace: MONO, color: MUTED } },
  ], { x: 7.47, y: 2.82, w: 4.6, h: 0.3, isTextBox: true, margin: 0,
       fontSize: 13.5, fontFace: "Calibri" });
  s.addText([
    { text: "539 × 0.179", options: { fontFace: MONO, color: INK } },
    { text: "  =  97 s needed", options: { fontFace: MONO, color: MUTED } },
  ], { x: 7.47, y: 3.18, w: 4.6, h: 0.3, isTextBox: true, margin: 0,
       fontSize: 13.5, fontFace: "Calibri" });

  s.addShape(pres.ShapeType.rect, {
    x: 7.47, y: 3.62, w: 4.6, h: 0.012, fill: { color: "D5D7DB" }, line: { width: 0 },
  });
  s.addText([
    { text: "Cut at 60 s. Needed 97 s.", options: { bold: true, color: INK } },
  ], { x: 7.47, y: 3.78, w: 4.6, h: 0.32, isTextBox: true, margin: 0,
       fontSize: 16, fontFace: "Cambria" });
  s.addText("A round number below the time the work takes is a configured timeout on an intermediary — not a platform outage.",
    { x: 7.47, y: 4.16, w: 4.6, h: 0.72, isTextBox: true, margin: 0,
      fontSize: 12.5, color: MUTED, fontFace: "Calibri" });

  rule(s, 5.45);
  s.addText([
    { text: "Galileo was never down. ", options: { bold: true, color: INK } },
    { text: "It answered small batches all day. The manual checklist could not see that, because no single console shows it.",
      options: { color: MUTED } },
  ], { x: M, y: 5.66, w: COLW, h: 0.5, isTextBox: true, margin: 0,
       fontSize: 14, fontFace: "Calibri" });

  s.addNotes(
    "This is the real failure the tool was built around. Note the pattern: size, not time of day. " +
    "39 records took 7 seconds, so 539 records needs about 97. The call was cut at 60. " +
    "A round 60-second ceiling below the work's actual duration is a configured timeout on " +
    "something in between — a gateway or proxy. No one console shows this, which is why " +
    "the manual process never found it."
  );
}

// ================================================================ 4. SOLUTION
{
  const s = (pres.addSection({ title: "Solution" }), pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" }));
  kicker(s, "The solution");
  s.addText("Paste the error. Get the whole answer", { placeholder: "title" });

  s.addText("One box. No consoles, no credentials, nothing to install on the systems being diagnosed.",
    { x: M, y: 1.62, w: 9.0, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const cards = [
    ["Root cause", "The failing layer, named — with the rule that decided it."],
    ["Confidence", "High, Medium or Inconclusive. Capped when we cannot see enough."],
    ["Evidence", "Every observation, with the source it came from."],
    ["Ruled out", "The six other causes it is not, and why."],
    ["Precedent", "Past incidents of the same shape, and whether the fix held."],
    ["The fix", "The runbook step — and what not to do."],
  ];
  cards.forEach(([h, b], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * 3.93, y = 2.3 + row * 1.52;
    s.addShape(pres.ShapeType.rect, {
      x, y, w: 3.6, h: 1.28, fill: { color: TINT }, line: { width: 0 },
      objectName: `card${i}`,
    });
    s.addText(String(i + 1).padStart(2, "0"), {
      x: x + 0.32, y: y + 0.2, w: 0.5, h: 0.24, isTextBox: true, margin: 0,
      fontSize: 10.5, bold: true, color: ACCENT, fontFace: MONO,
    });
    s.addText(h, { x: x + 0.32, y: y + 0.46, w: 3.0, h: 0.28, isTextBox: true,
                   margin: 0, fontSize: 15, bold: true, color: INK, fontFace: "Calibri" });
    s.addText(b, { x: x + 0.32, y: y + 0.74, w: 3.0, h: 0.46, isTextBox: true,
                   margin: 0, fontSize: 11.5, color: MUTED, fontFace: "Calibri" });
  });

  rule(s, 5.62);
  s.addText([
    { text: "Read-only by design. ", options: { bold: true, color: INK } },
    { text: "It never restarts anything, never remediates, never writes to a system it is diagnosing.",
      options: { color: MUTED } },
  ], { x: M, y: 5.83, w: COLW, h: 0.4, isTextBox: true, margin: 0,
       fontSize: 14, fontFace: "Calibri" });

  s.addNotes(
    "You paste the error block and get six things back, not one. The last two are what " +
    "change the response: precedent tells you whether this has happened before and whether " +
    "the fix held; the runbook tells you what not to do, which is usually where time is lost. " +
    "And it is read-only — nothing to clear with risk review about write access."
  );
}

// ================================================================ 5. DIFFERENT
{
  const s = (pres.addSection({ title: "Difference" }), pres.addSlide({ masterName: "CONTENT", sectionTitle: "Difference" }));
  kicker(s, "How it is different");
  s.addText("Code decides. The model writes", { placeholder: "title" });

  s.addText("Most AI log tools ask a language model what broke. We never do. The cause is decided by rules over measured facts; the model only turns that decision into a sentence.",
    { x: M, y: 1.6, w: 10.4, h: 0.62, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  const headY = 2.52;
  s.addText("A CONVENTIONAL AI LOG TOOL", {
    x: M, y: headY, w: 5.3, h: 0.26, isTextBox: true, margin: 0,
    fontSize: 10, bold: true, charSpacing: 1.8, color: MUTED, fontFace: "Calibri",
  });
  s.addText("THIS", {
    x: 7.15, y: headY, w: 5.3, h: 0.26, isTextBox: true, margin: 0,
    fontSize: 10, bold: true, charSpacing: 1.8, color: ACCENT, fontFace: "Calibri",
  });
  rule(s, headY + 0.32, M, 5.3, "E3E5E8");
  rule(s, headY + 0.32, 7.15, 5.28, ACCENT);

  const pairs = [
    ["The model guesses the root cause", "A rules engine decides it. The model is never asked"],
    ["Confident even when wrong", "Says “I don’t know” when nothing matches"],
    ["Cannot show why", "Every claim carries the evidence and its source"],
    ["Dies when the AI is down", "Works with the AI switched off entirely"],
    ["A black box to a risk reviewer", "The decision is 8 rules in a file anyone can read"],
  ];
  pairs.forEach(([a, b], i) => {
    const y = headY + 0.52 + i * 0.6;
    s.addText(a, { x: M, y, w: 5.3, h: 0.46, isTextBox: true, margin: 0,
                   fontSize: 13.5, color: MUTED, fontFace: "Calibri", valign: "middle" });
    s.addText(b, { x: 7.15, y, w: 5.28, h: 0.46, isTextBox: true, margin: 0,
                   fontSize: 13.5, color: INK, bold: true, fontFace: "Calibri",
                   valign: "middle" });
  });

  s.addText("If the model hallucinates, you get an awkward sentence — never a wrong root cause.",
    { x: M, y: 6.42, w: COLW, h: 0.4, isTextBox: true, margin: 0,
      fontSize: 14, italic: true, color: ACCENT, fontFace: "Cambria" });

  s.addNotes(
    "This is the slide to linger on. Everyone in this competition has an LLM reading logs. " +
    "The difference is where the decision is made. Ours is made by rules over measured facts, " +
    "which means it is reproducible, testable and auditable. The model only phrases it. " +
    "Switch the AI off and every answer is identical — just plainer wording."
  );
}

// ================================================================ 6. BEYOND
{
  const s = (pres.addSection({ title: "Beyond the fix" }), pres.addSlide({ masterName: "CONTENT", sectionTitle: "Beyond the fix" }));
  kicker(s, "Beyond the fix");
  s.addText("Each incident makes the next one cheaper", { placeholder: "title" });

  s.addText("Fixing today's failure is the floor. The tool also says how to stop it recurring, and why it was hard to diagnose in the first place.",
    { x: M, y: 1.6, w: 10.2, h: 0.62, isTextBox: true, margin: 0,
      fontSize: 15, color: MUTED, fontFace: "Calibri" });

  // Card A — prevention
  s.addShape(pres.ShapeType.rect, {
    x: M, y: 2.52, w: 5.5, h: 3.1, fill: { color: TINT }, line: { width: 0 },
    objectName: "preventCard",
  });
  s.addText("PREVENT RECURRENCE", {
    x: M + 0.4, y: 2.82, w: 4.7, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 10, bold: true, charSpacing: 2, color: ACCENT, fontFace: "Calibri" });
  s.addText("200", {
    x: M + 0.4, y: 3.10, w: 2.4, h: 0.96, isTextBox: true, margin: 0,
    fontSize: 54, color: INK, fontFace: MONO });
  s.addText("records per request", {
    x: M + 0.4, y: 4.10, w: 4.7, h: 0.26, isTextBox: true, margin: 0,
    fontSize: 13, color: MUTED, fontFace: "Calibri" });
  s.addText("60 s ceiling × 0.6 headroom ÷ 0.179 s per record", {
    x: M + 0.4, y: 4.40, w: 4.7, h: 0.26, isTextBox: true, margin: 0,
    fontSize: 11, color: MUTED, fontFace: MONO });
  s.addText("Calculated from the throughput measured in this log — so it stays correct when the system gets faster or slower. Plus code, config, monitoring and process actions from our own runbooks.",
    { x: M + 0.4, y: 4.74, w: 4.7, h: 0.80, isTextBox: true, margin: 0,
      fontSize: 12, color: MUTED, fontFace: "Calibri" });

  // Card B — log quality
  s.addShape(pres.ShapeType.rect, {
    x: 6.93, y: 2.52, w: 5.5, h: 3.1, fill: { color: TINT }, line: { width: 0 },
    objectName: "loggingCard",
  });
  s.addText("LOGGING QUALITY", {
    x: 7.33, y: 2.82, w: 4.7, h: 0.24, isTextBox: true, margin: 0,
    fontSize: 10, bold: true, charSpacing: 2, color: ACCENT, fontFace: "Calibri" });
  s.addText([
    { text: "5", options: { color: INK } },
    { text: "/10", options: { color: MUTED, fontSize: 30 } },
  ], { x: 7.33, y: 3.10, w: 2.6, h: 0.96, isTextBox: true, margin: 0,
       fontSize: 54, fontFace: MONO });
  s.addText("practices present", {
    x: 7.33, y: 4.10, w: 4.7, h: 0.26, isTextBox: true, margin: 0,
    fontSize: 13, color: MUTED, fontFace: "Calibri" });
  s.addText("No duration · no correlation id · size off the error",
    { x: 7.33, y: 4.40, w: 4.7, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 10.5, color: MUTED, fontFace: MONO });
  s.addText("Our code never records how long a job takes. That is why a sync slowing down for weeks was invisible until the day it broke. Each gap states what it cost this investigation.",
    { x: 7.33, y: 4.74, w: 4.7, h: 0.80, isTextBox: true, margin: 0,
      fontSize: 12, color: MUTED, fontFace: "Calibri" });

  rule(s, 6.0);
  s.addText([
    { text: "Three outputs per incident instead of one: ", options: { bold: true, color: INK } },
    { text: "the fix, the prevention plan, and the logging gaps that slowed us down.",
      options: { color: MUTED } },
  ], { x: M, y: 6.2, w: COLW, h: 0.4, isTextBox: true, margin: 0,
       fontSize: 14, fontFace: "Calibri" });

  s.addNotes(
    "This is what turns firefighting into something that compounds. The 200 is calculated, " +
    "not typed — change the measured throughput and it changes. And the logging score is " +
    "feedback to our own developers: we score 5 out of 10, and the biggest gap is that we " +
    "never log duration, which is exactly why this failure was invisible for weeks."
  );
}

// ================================================================ 7. CLOSE
{
  const s = (pres.addSection({ title: "Close" }), pres.addSlide({ masterName: "DARK", sectionTitle: "Close" }));

  s.addText("BUILT TO SURVIVE REVIEW", {
    x: M, y: 1.0, w: COLW, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 11, bold: true, charSpacing: 3, color: ACCENT, fontFace: "Calibri",
  });
  s.addText("Not a demo. A tool our team can run on Monday", {
    x: M, y: 1.42, w: 10.6, h: 0.75, isTextBox: true, margin: 0,
    fontSize: 36, color: PAPER, fontFace: "Cambria",
  });

  const stats = [
    ["264", "automated tests", "All pass offline, with no API key."],
    ["0", "AI in the decision", "Stages 1–6 are plain Python."],
    ["4", "config files", "Another team adapts it without code."],
    ["19", "grounded lookups", "The chat cannot reach anything else."],
  ];
  stats.forEach(([n, l, d], i) => {
    const x = M + i * 2.98;
    s.addText(n, { x, y: 2.75, w: 2.6, h: 0.86, isTextBox: true, margin: 0,
                   fontSize: 52, color: PAPER, fontFace: MONO });
    s.addText(l, { x, y: 3.62, w: 2.6, h: 0.28, isTextBox: true, margin: 0,
                   fontSize: 13.5, bold: true, color: "C9CCD1", fontFace: "Calibri" });
    s.addText(d, { x, y: 3.92, w: 2.6, h: 0.62, isTextBox: true, margin: 0,
                   fontSize: 11.5, color: "7A818A", fontFace: "Calibri" });
  });

  s.addShape(pres.ShapeType.rect, {
    x: M, y: 5.05, w: COLW, h: 0.012, fill: { color: "3A3F46" }, line: { width: 0 },
  });

  s.addText("Code decides what happened. The model explains it.", {
    x: M, y: 5.32, w: 8.4, h: 0.45, isTextBox: true, margin: 0,
    fontSize: 21, italic: true, color: PAPER, fontFace: "Cambria",
  });
  s.addText("That is the whole reliability argument — and the reason this can run in a bank.", {
    x: M, y: 5.82, w: 7.9, h: 0.35, isTextBox: true, margin: 0,
    fontSize: 13.5, color: "7A818A", fontFace: "Calibri",
  });

  s.addText("TEAM POTENTIAL", {
    x: W - M - 3.2, y: 5.85, w: 3.2, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 12, bold: true, charSpacing: 2.6, color: ACCENT,
    fontFace: "Calibri", align: "right",
  });

  s.addNotes(
    "Close on deployability. 264 tests that run with no network and no API key. Zero AI in " +
    "the decision path. Four config files mean another team adopts this by editing JSON. " +
    "And the whole thing is read-only. Happy to demo it live — paste a log and it answers " +
    "in about two seconds."
  );
}

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
  console.log("wrote " + OUT);
});
