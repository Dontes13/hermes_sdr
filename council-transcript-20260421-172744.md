# LLM Council Transcript
**Date:** April 21, 2026
**Topic:** Which AI class project to build — Lead Quality Scorer (A) vs. Enrichment Budget Optimizer (B)

---

## Original Question
Read over the context of this situation and recommend which project to build.

## Framed Question
Enrique is a student in an Intro to AI class and needs to pick ONE final project to build. The project is worth 100 points with this rubric: Report quality (30pts), Clarity & reproducibility (20pts), Solves the problem (20pts), Originality (15pts), Accuracy of results (15pts).

He has a real B2B sales platform called Hermes that prospects leads, enriches them via web scraping + LLMs, drafts cold emails, and sends them. He wants the project to connect to this real system. He'll generate a synthetic dataset either way.

**Option A: Lead Quality Scorer (Classification)** — Train a binary classifier to predict whether a lead will reply based on features available at prospect time (Google rating, review count, has_website, city, business_type, etc.). Compare logistic regression, decision tree, and random forest. Evaluate with ROC-AUC, confusion matrices, feature importance. Clean supervised learning problem.

**Option B: Enrichment Budget Optimizer (Genetic Algorithm)** — Given a pool of ~200 leads with estimated value and variable enrichment cost, use a GA to select the optimal subset to enrich under a daily budget constraint (a 0/1 knapsack variant). Binary chromosome, tournament selection, uniform crossover, bit-flip mutation. Compare GA vs greedy baseline, run parameter sensitivity and scaling experiments.

Which project should he build? Consider: which scores higher on the rubric, which is more feasible for one student to complete well, which is more impressive for an Intro to AI class, and which connects more meaningfully to the real Hermes system.

---

## Advisor Responses

### The Contrarian → Option A
Option B has a fatal flaw that Enrique is probably not seeing: it's an optimization problem dressed up as AI, and an intro-level grader will notice.

The 0/1 knapsack problem is solved. A greedy heuristic sorted by value-to-cost ratio will get within a few percent of optimal for 200 items. When Enrique runs his GA against the greedy baseline, the results will be nearly identical — maybe the GA wins by 1-2%. The grader asks: "Why not just use dynamic programming, which gives the exact answer in polynomial time for this size?" Enrique has no good answer. He built a cannon to kill a fly. That kills him on "Solves the problem" (20pts) because the problem didn't need a GA to be solved. Originality also suffers because knapsack-via-GA is a textbook exercise, not a novel application.

Worse, the "connection to Hermes" is fabricated either way since he's generating synthetic data, but Option B's connection is especially thin. He's optimizing over made-up costs and made-up lead values. There's no ground truth to validate against. What does "accuracy of results" even mean when you're comparing a GA to a greedy algorithm on fake numbers? He'll struggle to fill 15 points there.

Option A has a real dependent variable — did the lead reply or not. That's measurable. The feature set maps directly to what Hermes collects during prospecting. The model comparison (logistic regression vs. trees vs. forest) is exactly what intro AI courses want to see. Feature importance analysis tells a genuine business story. ROC-AUC gives him a concrete accuracy metric.

Option A's biggest risk is boring results — all models perform similarly on synthetic data. He needs to engineer the synthetic dataset carefully to create meaningful signal.

But "boring with solid execution" scores 85+. "Clever but unjustified" scores 70. **Pick Option A.**

### The First Principles Thinker → Option B
The real question isn't "which project scores higher" — it's "which project demonstrates that Enrique actually learned AI?" Strip away the Hermes connection, the cool factor, the real-world narrative. What does the rubric reward?

The rubric gives 30 points to the report and 20 to clarity/reproducibility. That's half the grade on writing and methodology, not results. A genetic algorithm project has dramatically more to write about: encoding scheme, selection pressure, crossover operators, mutation rates, convergence analysis, parameter sensitivity. Each design choice demands justification. A classification project? You call sklearn, print metrics, done. The report writes thin.

"Solves the problem" (20pts) — what problem does the lead scorer actually solve? It predicts replies using features available before enrichment. With synthetic data and no real outcome labels, the "problem" is fabricated end-to-end. The optimizer solves a concrete, defensible problem: budget-constrained selection. The problem statement is mathematically clean. The solution is verifiable.

Originality (15pts) — binary classification with sklearn is the most common intro AI project on Earth. A knapsack-variant GA applied to a real business constraint? That's genuinely unusual for an intro class.

Accuracy (15pts) — counterintuitively, this favors B. GA convergence toward known optimal solutions gives you provable accuracy metrics. Classification accuracy on synthetic data with no ground truth is meaningless theater.

The deeper issue: Option A looks like AI but is really just API calls. Option B looks simple but is actually algorithmic thinking. An intro AI class should reward the latter. **Build the optimizer.**

### The Expansionist → Option B
Option B has compounding upside across every rubric dimension. Option A has a ceiling — train a classifier, get AUC, done. No "what if this works even better than expected" story.

Originality (15pts): every other student in an Intro to AI class is building a classifier. A genetic algorithm solving a real resource allocation problem? The professor will notice. That alone could be worth 5+ extra points over A.

Solves the problem (20pts): B solves a problem that actually matters to Hermes right now. Enrique has a real budget constraint on enrichment API calls. This isn't hypothetical — he could deploy this tomorrow.

Report quality (30pts): B gives you more to write about — convergence plots, parameter sensitivity across mutation rate/population size/generations, scaling experiments, comparison against greedy and random baselines.

The hidden opportunity: extend to multi-objective optimization as a bonus section. That's a section that screams ambition.

Feasibility is fine. A basic GA for 0/1 knapsack is ~150 lines of Python. The complexity comes from experiments and analysis — exactly where you earn points. **Take the shot with more upside.**

### The Outsider → Option B
Option A sounds like a Kaggle tutorial. Binary classifier, compare three models, show ROC curves. Every intro AI student does this. The connection to Hermes is cosmetic — you're classifying synthetic data with made-up reply labels. A grader who's seen fifty projects will recognize the template instantly.

Option B is a different animal. The problem formulation itself requires thought — defining chromosomes, fitness functions, constraints. That's not something you copy from a scikit-learn quickstart. The knapsack framing is concrete and easy for a grader to understand, but the implementation demands real design decisions. Tournament selection parameters, crossover rates, mutation rates, convergence criteria — each one is a knob you have to justify.

Clarity & reproducibility (20pts) is straightforward because GAs are self-contained — no external dependencies. Originality (15pts) is where B dominates. Accuracy (15pts) works because you compare against a greedy baseline.

The feasibility concern about GAs is wrong. A basic GA on 200 binary variables is a weekend of coding. **Build B.**

### The Executor → Option B
Monday morning, here's what Enrique does for Option A: generate synthetic lead data, slap labels on it, run three sklearn classifiers, plot ROC curves, write it up. That's a weekend project, maybe two days. The problem? The labels are fake. "Accuracy of results" (15pts) becomes meaningless when your ground truth is synthetic.

Option B has a concrete, executable path. Every step is a clear afternoon task. The synthetic data problem disappears because the GA doesn't need "real" labels — it just needs plausible cost and value numbers derivable from actual Hermes enrichment costs. The connection to Hermes is direct: "I built a tool that decides which leads to spend money enriching."

For the rubric: Solves the problem — GA clearly solves budget allocation. Originality — GA knapsack applied to sales ops beats "I ran random forest" every time. Accuracy — he can mathematically verify against brute force on small instances. **Build Option B. Start coding today.**

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Review 1
**Strongest:** Response A — the only one that stress-tests Option B on its weakest point (greedy nearly matches GA). Concrete technical argument, not vibes.

**Biggest blind spot:** Response B — claims classification "writes thin" while ignoring feature engineering, class imbalance, threshold tuning. Also claims GA convergence is "provable accuracy" — convergence toward an optimum is not accuracy on the rubric.

**All missed:** Synthetic data asymmetry — for B, synthetic costs are structurally fine because GA correctness is input-independent. Also missed that combining both (classifier feeds GA values) could be powerful.

### Review 2
**Strongest:** Response A — engages with grader's actual perspective, which determines the score.

**Biggest blind spot:** Response B — claims classification accuracy on synthetic data is "meaningless theater" while GA fitness on synthetic data is equally synthetic.

**All missed:** The instructor's course objectives. Intro AI courses emphasize supervised learning. Option B may fall outside course scope entirely — off-topic rather than original.

### Review 3
**Strongest:** Response A — thinks from grader's perspective. "Why not DP?" is a concrete, likely challenge.

**Biggest blind spot:** Response B — wrong about classification reporting being thin.

**All missed:** Synthetic data risk asymmetry. For A, labels can be designed to produce meaningful results. For B, synthetic costs make results unfalsifiable.

### Review 4
**Strongest:** Response A — maps rubric directly to the "why GA?" challenge (35 combined points at risk).

**Biggest blind spot:** Response B — mischaracterizes both options.

**All missed:** Synthetic data for B is unfalsifiable, and grader can't assess whether output is meaningful.

### Review 5
**Strongest:** Response A — identifies core technical risk.

**Biggest blind spot:** Response B — inflates GA's report advantage while ignoring A's natural report structure.

**All missed:** Accuracy paradox — you need DP to verify GA results, which proves GA unnecessary.

---

## Chairman's Verdict

### Where the Council Agrees
Every advisor agrees Option B produces a richer report. They also agree Option A is safer and more conventional. 4/5 advisors favor B, but the lone dissenter raises the strongest technical objection. All 5 peer reviewers identify the Contrarian's argument as the strongest contribution.

### Where the Council Clashes
Is originality a strength or liability in an intro course? The majority sees A as ceiling-limited. The Contrarian argues originality that can't justify itself costs more than it gains. This is a disagreement about grader psychology — majority assumes grader rewards ambition, Contrarian assumes grader rewards appropriateness.

### Blind Spots the Council Caught
1. **The accuracy paradox** — verifying GA correctness requires DP/brute force, which proves GA unnecessary.
2. **Course scope risk** — GA may be outside course objectives; "off-topic" is worse than "conventional."
3. **Synthetic data asymmetry** — A's labels can be engineered for meaningful separation; B's costs are unfalsifiable.

### The Recommendation
**Pick Option A.** The peer reviews broke the tie. "Solves the problem" (20pts) + "Accuracy" (15pts) = 35 points that are straightforward with A and vulnerable with B. Option A with strong execution: 85-92. Option B: 72-95 depending on the grader. Take the lower variance path.

### The One Thing to Do First
Design the synthetic dataset schema — define 8-10 features, set 15-20% reply rate for realistic class imbalance, write the data generation function with a known logistic model underneath so ground truth is controlled and results are interpretable.
