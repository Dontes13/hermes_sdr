# LLM Council Transcript
**Date:** April 21, 2026
**Topic:** Grade prediction and improvement suggestions for Lead Quality Scorer project spec

---

## Original Question
Review the spec, try to think what grade I would get if I coded this and then turned it in. Assuming the report is well written. Also give suggestions.

## Framed Question
Enrique is a student in an Intro to AI class (IFSA CS38-09, Spring 2026). He needs to build a final project worth 100 points with this rubric: Report quality (30pts), Clarity & reproducibility (20pts), Solves the problem (20pts), Originality (15pts), Accuracy of results (15pts).

He's building a Lead Quality Scorer — a binary classifier predicting whether a B2B sales lead will reply to a cold email, using synthetic data from a known logistic model, comparing perceptron/decision tree/logistic regression/random forest. The spec has 8 features from Google Places data, a production scoring module for his real platform Hermes, and plans to integrate the scorer into the campaign runner.

Class content covered: PEAS framework, agent types, environment classification, supervised learning, perceptrons, decision trees, linear regression.

Review this spec and answer: (1) What grade would this get? (2) Biggest risks? (3) How to push higher?

---

## Advisor Responses

### The Contrarian → 78-84/100
The synthetic data is the fatal flaw — you're generating data from a logistic model then "discovering" logistic regression fits best. That's circular. The professor will see through this immediately. You're not solving a real problem — you're solving a problem you manufactured to have a known answer. That costs you on Solves the Problem (20pts) and Originality (15pts).

The noise feature trick (is_insurance with coefficient 0) is transparent — it's textbook stuff, not impressive. Comparing four off-the-shelf classifiers on synthetic data is a standard homework exercise, not a final project.

Suggestions: Use real Hermes reply data even a small subset. Add calibration curve. Drop one classifier and add a meaningful baseline (what's Hermes's current conversion rate without scoring?). Discuss where synthetic assumptions break down against real patterns. Safe gets you a B.

### The First Principles Thinker → 82-88/100
The project over-engineers a production system while under-investing in demonstrating course concepts. The professor taught PEAS framework, agent types, environment classification — the spec treats these as irrelevant rather than the substance.

Synthetic data is a tautology. You've pre-determined your results. This directly threatens Accuracy of Results (15pts) and Solves the Problem (20pts).

Missing connection to course content: Where's the PEAS analysis? Where's the environment classification? The professor wants to see frameworks applied, not just sklearn imported.

Suggestions: Use 50-200 real leads as validation set. Add PEAS decomposition and agent-type analysis. Implement perceptron step-by-step (not just sklearn) — that's what was coded in class. Acknowledge synthetic limitation rigorously. Strip away production language — professor grades learning demonstration, not software engineering.

### The Expansionist → 88-93/100 (potential 97+)
The spec has compounding upside. Hidden gold: Enrique has real production data he could validate against. The production scoring module sets this apart from every other student. The noise feature isn't just a sanity check — it's a built-in ablation study.

The synthetic-to-real transfer story is the real differentiator: "I built a simulation, validated my pipeline, and here's my plan to close the sim-to-real gap." That's how ML teams at companies operate.

Suggestions: Add calibration plot (10 lines of code). Compare synthetic data distribution to real Hermes data. Add precision-recall curve alongside ROC-AUC since class imbalance makes PR more informative. The ceiling is higher than the spec aims for.

### The Outsider → 82-88/100
The synthetic data does all the heavy lifting. A grader with fresh eyes will ask: "Did you solve a problem or did you build a puzzle and then solve your own puzzle?"

Random forest and logistic regression weren't class topics — could go either way. Impressive initiative or "did you just import sklearn and call .fit()?" If the report doesn't show understanding of what's happening inside these models mathematically, it'll lose Clarity & Reproducibility points.

The production integration piece is vaporware in an academic submission without real data validation.

Suggestions: Run on 50-100 real Hermes leads. Add a limitations section. Show the perceptron math by hand for one example — tie it directly to lecture content. Frame the noise feature as an explicit experiment, not a footnote.

### The Executor → 82-88/100
The spec is solid on paper — buildable in a weekend with guaranteed working output. Synthetic data guarantees something works on demo day. No dependency on messy real data that could blow up at midnight before the deadline.

Biggest risk: Report quality is 30 points and students always botch it. 90% of time on code, 10% on report — that's backwards for this rubric.

Suggestions: Write the report outline FIRST before touching code. Allocate 40% of total time to the report. Include a screenshot or mock of how the scorer would appear in Hermes (makes "solves the problem" tangible). Add calibration plot (5 lines of code). The risk isn't ambition — it's underinvesting in the writeup.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Review 1
**Strongest:** Response B — uniquely caught missing PEAS/environment classification. Correctly diagnoses the audience: professor grades learning, not production readiness.

**Biggest blind spot:** Response C — overestimates grade, mistakes aspiration for substance. No confirmed real data pipeline exists.

**All missed:** Clarity & Reproducibility (20pts) not concretely addressed — fixed seeds, dependency pinning, README. No "production readiness" rubric category exists, yet multiple responses spend time on production framing.

### Review 2
**Strongest:** Response B — correctly diagnoses audience. Professor grades learning demonstration, not production readiness.

**Biggest blind spot:** Response C — dramatically overestimates, provides false confidence. Fails to flag circularity problem.

**All missed:** No response maps rubric categories to specific deliverables. Report Quality at 30pts barely addressed by anyone.

### Review 3
**Strongest:** Response B — catches missing PEAS and environment classification.

**Biggest blind spot:** Response C — misjudges academic context. A professor teaching intro AI will penalize circular methodology.

**All missed:** Project lacks search, planning, or knowledge representation components — central Intro to AI topics. No statistical significance testing between models.

### Review 4
**Strongest:** Response B — catches missing PEAS.

**Biggest blind spot:** Response C — dangerously optimistic. Assumes real data exists and is usable when spec doesn't confirm this.

**All missed:** No one asks about required submission format/deliverables from the professor. Format determines how rubric categories are evaluated.

### Review 5
**Strongest:** Response B — catches missing PEAS.

**Biggest blind spot:** Response C — ignores circularity problem entirely.

**All missed:** Clarity & Reproducibility (20pts) not concretely addressed. No ethical considerations section mentioned.

---

## Chairman's Verdict

### Where the Council Agrees
Synthetic data circularity is the single biggest intellectual risk. Four of five advisors flagged this independently: generating data from a logistic model, then comparing classifiers, guarantees logistic regression wins. The professor will see through it. This undermines "Solves the Problem" (20pts) and "Originality" (15pts) simultaneously.

The missing PEAS analysis is free points being left on the table. Every peer review identified the First Principles Thinker's argument as strongest precisely because this observation is both correct and actionable. Adding PEAS costs thirty minutes and directly demonstrates course mastery.

Real data validation — even a tiny amount — transforms the project. Four advisors converged on 50-200 real leads from Hermes.

Report quality is dangerously under-planned for a 30-point category.

### Where the Council Clashes
Grade range: 78 vs. 93. The Contrarian predicts 78-84. The Expansionist predicts 88-93 with upside to 97. This 15-point spread reflects different assumptions about the grader.

The Contrarian is right about the floor — if the report is thin, circularity unaddressed, and PEAS missing, a rigorous professor lands in the low 80s. The Expansionist is right about the ceiling — but only if additions not currently in the spec are executed. The peer reviews unanimously flagged the Expansionist as the biggest blind spot for mistaking aspiration for deliverable.

Whether "beyond-syllabus" models help or hurt depends on report framing. If Enrique shows he understands why random forest works (ensemble of decision trees, which were taught), it helps. If he just calls the constructor and reports accuracy, it's neutral at best.

### Blind Spots the Council Caught
1. Clarity and Reproducibility (20pts) was essentially unaddressed by all five advisors — fixed seeds, pinned dependencies, README, clean notebook organization.
2. No advisor mapped rubric categories to specific deliverables — the most useful analysis possible was missing.
3. Project touches none of search, planning, or knowledge representation — central Intro to AI topics beyond just ML.
4. No one asked about submission format or professor expectations.

### The Recommendation
**Predicted grade as currently specced: 80-85. With changes: 90-95.**

The project has a strong skeleton. But it optimizes for engineering impressiveness rather than academic demonstration, and has a circularity problem the professor will notice.

Priority changes:
1. Add PEAS decomposition and environment classification (+3-5 pts)
2. Validate on 50-100 real Hermes leads, or at minimum compare feature distributions (+5-8 pts)
3. Write the report outline before more code — structure it to the rubric (+5-10 pts)
4. Lock down reproducibility: fixed seeds, pinned requirements, single-command reproduction (+3-5 pts)
5. Frame noise feature as deliberate ablation experiment (+1-2 pts)
6. Show one perceptron training pass by hand — proves understanding of what was taught (+2-3 pts)

The project does not need more models, more features, or production screenshots. It needs to demonstrate that Enrique learned the course material and can apply it rigorously.

### The One Thing to Do First
Write the full report outline — section headings, contents, and which rubric category each section serves — before touching any more code.
