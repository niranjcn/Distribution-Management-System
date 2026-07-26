# OpenCode Plans — Complete Reference

> A comprehensive guide to all planning capabilities in the opencode ecosystem.

---

## 1. Plan Mode (Built-in)

OpenCode has a native **Plan Mode** that disables its ability to make file changes and instead suggests *how* to implement a feature.

- **Activation:** Press `Tab` to toggle between Plan mode and Build mode
- **Environment variables:** `CLAUDE_PLAN_FILE` or `GSTACK_PLAN_MODE` (values: `active` / `inactive`)
- **Behavior:** Only plan-informing operations are allowed (reads, searches, writes to the plan file, generated artifacts)
- **Use when:** You want to design before building

---

## 2. Planning Skills (gstack Suite)

### 2.1 `/autoplan` — Auto-Review Pipeline

One-command automated review pipeline. Reads all four review skills (CEO, design, eng, DX) from disk and runs them sequentially with auto-decisions using 6 decision principles. Surfaces taste decisions at a final approval gate.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | `autoplan`, `auto review`, `run all reviews`, `review this plan automatically`, `make the decisions for me` |
| **Voice** | `auto plan`, `automatic review` |
| **Category** | Pipeline / Orchestration |

**Workflow:** CEO Review → Design Review → Eng Review → DX Review → Approval Gate

---

### 2.2 `/plan-ceo-review` — CEO / Founder Plan Review

Rethinks the problem, finds the 10-star product, challenges premises, expands scope when it creates a better product.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | `think bigger`, `expand scope`, `strategy review`, `rethink this`, `is this ambitious enough` |
| **Category** | Strategy / Product |

**Four modes:**

| Mode | Description |
|------|-------------|
| **SCOPE EXPANSION** | Dream big, push scope UP, envision the platonic ideal |
| **SELECTIVE EXPANSION** | Hold current scope as baseline, cherry-pick expansions |
| **HOLD SCOPE** | Maximum rigor, make it bulletproof, no expansion or reduction |
| **SCOPE REDUCTION** | Strip to essentials, find minimum viable version |

---

### 2.3 `/plan-eng-review` — Engineering Plan Review

Eng manager-mode plan review. Locks in the execution plan — architecture, data flow, diagrams, edge cases, test coverage, performance. Walks through issues interactively with opinionated recommendations.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | `review the architecture`, `engineering review`, `lock in the plan`, `does this design make sense` |
| **Voice** | `tech review`, `technical review`, `plan engineering review` |
| **Category** | Architecture / Engineering |

**Areas covered:**

- Architecture design
- Data flow diagrams
- Edge case analysis
- Test coverage planning
- Performance considerations
- Database schema review
- API design review

---

### 2.4 `/plan-design-review` — Design Plan Review

Designer's eye plan review. Rates each design dimension 0-10, explains what would make it a 10, then fixes the plan to get there. Uses an AI mockup generator to create visual mockups from design briefs.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | `review the design plan`, `design critique` |
| **Category** | Design / UI/UX |

**Dimensions scored:**

- Visual hierarchy
- Typography
- Color system
- Spacing / Layout
- Responsive behavior
- Accessibility
- Motion / Interaction
- Consistency

---

### 2.5 `/plan-devex-review` — Developer Experience Plan Review

Interactive developer experience plan review. Explores developer personas, benchmarks against competitors, designs magical moments, traces friction points before scoring.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | `DX review`, `developer experience audit`, `devex review`, `API design review` |
| **Voice** | `dx review`, `developer experience review`, `devex audit`, `API design review`, `onboarding review` |
| **Category** | Developer Experience |

**Three modes:**

| Mode | Description |
|------|-------------|
| **DX EXPANSION** | Competitive advantage — go beyond expectations |
| **DX POLISH** | Bulletproof every touchpoint |
| **DX TRIAGE** | Critical gaps only — minimum viable DX |

**Reference:** Includes a DX Hall of Fame with gold standards from Stripe, Vercel, Clerk, Supabase, Firebase, Twilio, GitHub CLI, Bun, and more.

---

### 2.6 `/plan-tune` — Question Tuning & Developer Profile

Self-tuning question sensitivity + developer psychographic for gstack. Reviews which `AskUserQuestion` prompts fire across gstack skills, sets per-question preferences.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | `tune questions`, `stop asking me that`, `too many questions`, `show my profile`, `developer profile`, `turn off question tuning` |
| **Category** | Self-tuning / Configuration |

**Features:**

- Per-question preferences: `never-ask`, `always-ask`, `ask-only-for-one-way`
- Dual-track profile inspection (declared vs. behavioral)
- Dream cycle distillation of free-text answers
- Question log review

---

### 2.7 `/spec` — Spec Authoring

Turns vague intent into a precise, executable spec in five phases. Files the issue, optionally spawns a sub-agent in a fresh worktree, and lets `/ship` close the source issue on merge.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | `spec this out`, `file an issue`, `write up a ticket`, `make this a GitHub issue`, `turn this into a backlog item` |
| **Category** | Documentation / Backlog |

**Phases:**

1. Intent clarification
2. Requirement breakdown
3. Technical approach
4. Acceptance criteria
5. Issue filing

---

## 3. Supporting Skills (Feed into Planning)

### 3.1 `/office-hours` — Product Ideation / Brainstorming

YC-inspired office hours. Two modes:

| Mode | Description |
|------|-------------|
| **Startup mode** | Six forcing questions: demand reality, status quo, desperate specificity, narrowest wedge, observation, future-fit |
| **Builder mode** | Design thinking brainstorming for side projects, hackathons, learning, open source |

**Trigger:** `brainstorm this`, `I have an idea`, `help me think through this`, `office hours`, `is this worth building`

**Proactive:** Invoked when the user describes a new product idea before any code is written. Use before `/plan-ceo-review` or `/plan-eng-review`.

---

### 3.2 `/design-consultation` — Design System Creation

Design consultation: understands your product, researches the landscape, proposes a complete design system (aesthetic, typography, color, layout, spacing, motion), and generates font+color preview pages. Creates `DESIGN.md` as the project's design source of truth.

**Trigger:** `design system`, `brand guidelines`, `create DESIGN.md`

**Proactive:** Suggested when starting a new project's UI with no existing design system.

---

## 4. The Full Workflow

```
Idea → /office-hours  →  Spec →  Review Loop  →  /ship
                                       │
                          ┌────────────┼────────────┐
                    /plan-ceo      /plan-eng   /plan-design
                    -review        -review     -review
                          │
                    /autoplan (all-in-one)
```

**Typical first loop:**

1. `/office-hours` or `/spec` — shape the idea
2. `/plan-eng-review` — lock the architecture
3. `/plan-ceo-review` — validate direction
4. `/plan-design-review` — polish the UX
5. `/autoplan` — final automated gate
6. `/ship` — build and ship

---

## 5. Reference: Plan Mode Activation

| Method | Details |
|--------|---------|
| **Tab key** | Toggle between Plan and Build modes (UI) |
| `CLAUDE_PLAN_FILE` | Environment variable pointing to a plan file |
| `GSTACK_PLAN_MODE=active` | Environment variable to force plan mode |

---

## 6. Complete Skill Inventory (55 skills)

| # | Skill | Description |
|---|-------|-------------|
| 1 | **gstack** | Master router for the gstack skill suite |
| 2 | **autoplan** | Automated full review pipeline |
| 3 | **benchmark** | Performance regression detection |
| 4 | **benchmark-models** | Cross-model LLM comparison |
| 5 | **browse** | Headless browser for QA testing |
| 6 | **canary** | Post-deploy canary monitoring |
| 7 | **careful** | Safety guardrails for destructive commands |
| 8 | **claude** | Claude Code CLI wrapper |
| 9 | **context-restore** | Restore working context |
| 10 | **context-save** | Save working context |
| 11 | **cso** | Chief Security Officer security audit |
| 12 | **design-consultation** | Design system consultation |
| 13 | **design-html** | Production-quality HTML/CSS from designs |
| 14 | **design-review** | Live visual QA audit |
| 15 | **design-shotgun** | Multi-variant design exploration |
| 16 | **devex-review** | Live developer experience audit |
| 17 | **diagram** | Architecture/flowchart diagram generation |
| 18 | **document-generate** | Documentation writing |
| 19 | **document-release** | Post-ship documentation sync |
| 20 | **freeze** | Restrict edits to a directory |
| 21 | **guard** | Full safety (careful + freeze) |
| 22 | **health** | Code quality dashboard |
| 23 | **investigate** | Systematic debugging with RCA |
| 24 | **ios-clean** | Remove iOS debug bridge |
| 25 | **ios-design-review** | iOS visual design audit |
| 26 | **ios-fix** | Autonomous iOS bug fixer |
| 27 | **ios-qa** | Live-device iOS QA |
| 28 | **ios-sync** | Regenerate iOS debug bridge |
| 29 | **land-and-deploy** | Merge + deploy + verify |
| 30 | **landing-report** | Read-only queue dashboard |
| 31 | **learn** | Manage project learnings |
| 32 | **make-pdf** | Markdown to PDF generation |
| 33 | **office-hours** | Product ideation / brainstorming |
| 34 | **open-gstack-browser** | Launch AI-controlled Chromium |
| 35 | **pair-agent** | Pair remote AI agent with browser |
| 36 | **plan-ceo-review** | CEO/founder plan review |
| 37 | **plan-design-review** | Design plan review |
| 38 | **plan-devex-review** | Developer experience plan review |
| 39 | **plan-eng-review** | Engineering plan review |
| 40 | **plan-tune** | Question tuning & developer profile |
| 41 | **qa** | QA test + fix bugs |
| 42 | **qa-only** | Report-only QA |
| 43 | **retro** | Engineering retrospective |
| 44 | **review** | Pre-landing PR review |
| 45 | **scrape** | Web page data extraction |
| 46 | **setup-browser-cookies** | Import browser cookies |
| 47 | **setup-deploy** | Configure deployment settings |
| 48 | **setup-gbrain** | Setup gbrain for the agent |
| 49 | **ship** | PR creation workflow |
| 50 | **skillify** | Codify scrape flows as skills |
| 51 | **spec** | Spec authoring & issue filing |
| 52 | **sync-gbrain** | Sync gbrain with repo |
| 53 | **unfreeze** | Clear freeze boundary |
| 54 | **gstack-upgrade** | Upgrade gstack skill suite |
| 55 | **customize-opencode** | Edit opencode's own configuration |

---

*Generated from opencode.ai docs and local gstack skill suite. Last updated: 2026-07-26.*
