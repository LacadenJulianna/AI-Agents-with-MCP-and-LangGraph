# Agentic SEO Skill — Reference Architecture

**Audience:** Developers reverse-engineering this skill to understand, customize, or port it to another platform.

**Skill version:** v3.0.1  
**File:** `docs/reverse-engineering-architecture.md`

---

## 1. Overview

The Agentic SEO Skill is an **LLM-first automated SEO analysis tool** designed for AI coding assistants (Claude Code, Codex, Cursor, Windsurf, etc.). Instead of hardcoding SEO checks in traditional code, it leverages the LLM as the primary analyst and uses Python scripts purely as **evidence collectors**.

### Five-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: SKILL.md (Orchestrator)                       │
│  Routes user intent → sub-skill → workflow              │
├─────────────────────────────────────────────────────────┤
│  Layer 2: resources/skills/ (16 Sub-Skill Files)        │
│  Tell the LLM what to check per domain                  │
├─────────────────────────────────────────────────────────┤
│  Layer 3: resources/agents/ (10 Specialist Agents)      │
│  Role definitions the LLM adopts for deep-dive analysis │
├─────────────────────────────────────────────────────────┤
│  Layer 4: scripts/ (89 Evidence Collectors)             │
│  Python scripts that collect structured data from URLs  │
├─────────────────────────────────────────────────────────┤
│  Layer 5: resources/references/ (Quality Gates)         │
│  Rubrics, thresholds, scoring configs, standards        │
└─────────────────────────────────────────────────────────┘
```

### What Makes It "Agentic"

The skill works because **the LLM drives the analysis**, not the scripts. The Python scripts are optional evidence sources — the LLM can (and does) analyze a page using its own reading tool (`read_url_content`). Scripts add deterministic verification (e.g., "is the HTTP status really 200?"). This means:

- The skill degrades gracefully when scripts fail
- The LLM provides reasoning and judgment, not just data aggregation
- Adding new checks is as simple as editing a Markdown file

---

## 2. SKILL.md — The Orchestrator

### File: `SKILL.md` (369 lines)

This is **the master instruction file**. When installed as a skill, the AI coding assistant loads this file and follows its instructions when the user mentions SEO keywords.

### How Routing Works

The file defines a **Deterministic Trigger Mapping**: user phrases like "run SEO audit", "check schema markup", or "analyze this article" map to specific workflows:

| User says | LLM loads | What happens |
|-----------|-----------|-------------|
| "Run SEO audit on example.com" | `resources/skills/seo-audit.md` | Multi-page crawl, 6 agents, scoring |
| "Analyze this page" | `resources/skills/seo-page.md` | Single URL deep-dive (your Wikipedia audit) |
| "Check schema markup" | `resources/skills/seo-schema.md` | Schema-only analysis |
| "Core Web Vitals" | `resources/skills/seo-technical.md` | Performance-focused |

### Step-by-Step Workflow (from SKILL.md)

```
Step 1: Identify the Task        → Map user phrase to sub-skill
Step 2: Collect Evidence         → Run read_url_content + Python scripts
Step 3: Perform LLM Analysis     → Synthesize, find with evidence/impact/fix
Step 4: Run Verification Scripts → Baseline checks (robots, pagespeed, etc.)
Step 5: Delegate to Agents       → Read agent files, adopt specialist role
Step 6: Apply Quality Gates      → Load rubric, CWV thresholds, E-E-A-T rules
Step 7: Score and Report         → Weighted scoring → markdown files
Step 8: Deliver                  → FULL-AUDIT-REPORT.md + ACTION-PLAN.md
```

### Critical Rules Enforced

SKILL.md embeds hard rules the LLM must follow:

- **INP not FID** — FID was removed Sept 2024; never reference it
- **FAQ schema restricted** — Only for government/healthcare sites
- **HowTo deprecated** — Never recommend
- **JSON-LD only** — Never Microdata or RDFa
- **E-E-A-T everywhere** — Applies to all competitive queries since Dec 2025
- **Mobile-first complete** — 100% since July 2024

### Why This Works

The LLM is instructed to act as an SEO expert with a defined process. The SKILL.md file is the **process and the constraints** — it ensures every audit follows the same workflow regardless of which copy of the LLM runs it.

---

## 3. Sub-Skill Files (Layer 2)

### Directory: `resources/skills/` — 16 files

Each `.md` file tells the LLM what specific checks to perform for a domain of SEO. The files use YAML frontmatter for metadata and Markdown for instructions.

### File Inventory

| File | Purpose |
|------|---------|
| `seo-page.md` | Deep single-page analysis (title, meta, headings, links, schema, images, CWV) |
| `seo-audit.md` | Full multi-page audit orchestration with crawl + 6 agents |
| `seo-technical.md` | Crawlability, indexability, security, URLs, mobile, JS rendering |
| `seo-content.md` | Content quality & E-E-A-T assessment (Sept 2025 QRG) |
| `seo-schema.md` | Schema.org detection, validation & JSON-LD generation |
| `seo-sitemap.md` | XML sitemap analysis & generation |
| `seo-images.md` | Image optimization (alt text, formats, lazy loading, CLS) |
| `seo-geo.md` | Generative Engine Optimization (AI Overviews, ChatGPT, Perplexity) |
| `seo-aeo.md` | Answer Engine Optimization (Featured Snippets, PAA, Knowledge Panel) |
| `seo-links.md` | Link profile analysis (internal, backlinks, anchor text, orphan pages) |
| `seo-programmatic.md` | Programmatic SEO safeguards & quality gates |
| `seo-competitor-pages.md` | Comparison & alternatives page generation |
| `seo-hreflang.md` | International SEO / hreflang validation |
| `seo-plan.md` | Strategic SEO planning with topical clusters & industry templates |
| `seo-article.md` | Article data extraction & LLM-driven content optimization |
| `seo-github.md` | GitHub repository SEO (metadata, README, topics, traffic) |

### Anatomy of a Sub-Skill File

Using `seo-page.md` (which drove your Wikipedia audit) as the example:

```
---
name: seo-page
description: Deep single-page SEO analysis...
---

## On-Page SEO Checklist
- Title tag: 50-60 chars, primary keyword near front
- Meta description: 150-160 chars, includes CTA
- H1-H6 hierarchy: exactly one H1, no gaps
- URL: clean, hyphenated, keyword-aligned

## Content Quality
- Word count minimums by content type
- Flesch Reading Ease target
- E-E-A-T signals checklist

## Technical Elements
- Canonical tag presence and self-reference
- Meta robots directives
- Open Graph and Twitter Cards
- Hreflang tags

## Schema Markup
- JSON-LD detection
- Required property validation
- Known deprecated types to flag

...etc
```

The LLM reads this checklist and systematically applies it to the fetched page content. Each check produces a finding with evidence, impact, and fix recommendation.

### How the Wikipedia Audit Used These

For `https://en.wikipedia.org/wiki/Wikipedia`, the LLM loaded `seo-page.md` and checked:

- **Title tag:** Found "Wikipedia - Wikipedia" (21 chars) — flagged as short but acceptable for branded intent
- **Meta description:** Found missing — flagged as ❌ but marked low impact for Wikipedia
- **Headings:** Found 68 headings, H2 "Contents" before H1 — flagged as ⚠️ order issue
- **Images:** Found 45 images, 13 missing alt — flagged as ❌ gap
- **Schema:** Found valid Article JSON-LD with Q52 sameAs — ✅

---

## 4. Specialist Agents (Layer 3)

### Directory: `resources/agents/` — 10 files

These are **role definitions** the LLM adopts for deep-dive analysis. Each agent file describes a persona with specific expertise, tools, and focus areas.

### Agent Inventory

| File | Role | Focus |
|------|------|-------|
| `seo-technical.md` | Technical SEO Specialist | Crawlability, indexability, security, CWV, JS rendering |
| `seo-content.md` | Content Quality Reviewer | E-E-A-T, readability, thin content, AI citation readiness |
| `seo-performance.md` | Performance Specialist | LCP/INP/CLS breakdown, optimization recommendations |
| `seo-schema.md` | Schema Markup Specialist | Detection, validation, generation |
| `seo-sitemap.md` | Sitemap Specialist | XML validation, quality gates |
| `seo-visual.md` | Visual Analyst | Screenshots, above-the-fold, responsiveness |
| `seo-verifier.md` | Global Verifier | Deduplicate findings, suppress contradictions |
| `seo-github-analyst.md` | GitHub Analyst | Repo metadata, README, topics, trust |
| `seo-github-benchmark.md` | GitHub Benchmark | Query ranking, competitor intelligence |
| `seo-github-data.md` | GitHub Data | API/auth fallback, traffic archival |

### How Agents Work

When the LLM reaches Step 5 of the workflow, it reads the agent file and **assumes that persona**:

> "You are a **Technical SEO Specialist**. Your focus: crawlability, indexability, security, URL structure, mobile optimization, Core Web Vitals, and JavaScript rendering."

The agent file provides:
- A detailed checklist of what to inspect
- Which scripts to run for evidence
- How to interpret results
- What confidence labels to assign

### Why Agents Matter

Agents allow the LLM to **context-switch between specialties** within a single audit. The same LLM can be a "Technical SEO" for one section, a "Content Reviewer" for the next, and a "Schema Specialist" after that — without conflating the analysis.

---

## 5. Script Pipeline (Layer 4)

### Directory: `scripts/` — 89 Python files + 2 shell scripts

Scripts are **optional evidence collectors** that provide deterministic verification. The LLM runs them via bash and consumes their JSON output.

### Script Categories

| Category | Scripts | Purpose |
|----------|---------|---------|
| **Fetch & Parse** | `fetch_page.py`, `parse_html.py` | Get raw HTML, extract SEO elements |
| **Crawl** | `crawl_audit.py`, `internal_links.py`, `broken_links.py` | Multi-page crawling |
| **Technical** | `robots_checker.py`, `security_headers.py`, `redirect_checker.py`, `canonical_checker.py` | Infrastructure checks |
| **Performance** | `pagespeed.py`, `lcp_subparts.py`, `critical_request_chain.py`, `lighthouse_runner.py` | Core Web Vitals |
| **Content** | `article_seo.py`, `readability.py`, `entity_checker.py`, `duplicate_content.py` | Text analysis |
| **Schema** | `validate_schema.py`, `schema_template_generator.py`, `schema_required_props.py` | Structured data |
| **Sitemap** | `sitemap_checker.py`, `sitemap_generator.py` | XML sitemaps |
| **Images** | `image_inventory.py`, `image_weight_audit.py` | Image optimization |
| **Social** | `social_meta.py` | OG/Twitter Card validation |
| **GitHub** | `github_repo_audit.py`, `github_seo_report.py`, `github_competitor_research.py`, etc. | Repository SEO |
| **Reporting** | `generate_report.py`, `audit_runner.py`, `finding_verifier.py` | Output generation |
| **Validation** | `validate_skill_inventory.py`, `reference_freshness.py`, `pre_commit_seo_check.sh` | CI/CD quality |

### Key Scripts in Detail

#### `fetch_page.py`
- Fetches a URL with browser-like headers
- Follows redirects, handles timeouts
- Output: raw HTML file or stdout

#### `parse_html.py`
- Uses BeautifulSoup to extract:
  - Title tag, meta description, canonical, robots
  - All headings (H1–H6)
  - All links (internal, external, nofollow)
  - JSON-LD blocks
  - Open Graph and Twitter Card meta
  - Image tags with alt attributes
  - Schema.org script blocks
- Output: structured JSON

#### `generate_report.py` (1,766 lines)
- Runs all analysis scripts automatically
- Produces a self-contained interactive HTML dashboard
- Scoring, category breakdown, environment detection
- Output: `SEO-REPORT.html`

#### `audit_runner.py`
- CLI entry point for one-command full audit
- Reuses `generate_report.py`'s pipeline
- Output: `FULL-AUDIT-REPORT.md` + `ACTION-PLAN.md` + JSON

### Script Call Graph

For a single-page audit (your Wikipedia case):

```
audit_runner.py / generate_report.py
  ├── fetch_page.py          → /tmp/page.html
  ├── parse_html.py          → JSON of all SEO elements
  ├── robots_checker.py      → robots.txt analysis
  ├── sitemap_checker.py     → sitemap discovery
  ├── pagespeed.py           → Core Web Vitals (if API key available)
  ├── security_headers.py    → HSTS, CSP, etc.
  ├── redirect_checker.py    → redirect chain
  ├── social_meta.py         → OG / Twitter Cards
  ├── readability.py         → Flesch-Kincaid scores
  ├── image_inventory.py     → alt text, dimensions
  └── validate_schema.py     → JSON-LD validation
       └── finding_verifier.py  → dedup + prioritize
```

Each script returns JSON. The LLM reads these JSON outputs alongside its own `read_url_content` results and synthesizes everything into the final report.

---

## 6. References & Rubrics (Layer 5)

### Directory: `resources/references/` — 10 files

These are **standardized knowledge bases** the LLM consults during analysis. They ensure every audit uses consistent thresholds, rules, and output format.

### File Inventory

| File | Content |
|------|---------|
| `llm-audit-rubric.md` | Universal evidence format, confidence labels, severity, output contract |
| `cwv-thresholds.md` | Current Core Web Vitals thresholds (LCP, INP, CLS) |
| `eeat-framework.md` | E-E-A-T scoring criteria per Google Sept 2025 QRG |
| `quality-gates.md` | Word count minimums, unique content %, title/meta requirements |
| `schema-types.md` | Active, deprecated, and restricted schema.org types |
| `google-seo-reference.md` | Google SEO quick reference |
| `github-api-ops.md` | GitHub API operational guidance |
| `github-ranking-factors.md` | GitHub search ranking factors |
| `link-building.md` | Link building reference |
| `readme-audit-rubric.md` | README audit standards |

### The Rubric (`llm-audit-rubric.md`)

This is the **most important reference file**. It standardizes:

**Evidence Format:**
```
Finding:   One-line description of the issue
Evidence:  Specific element, metric, or HTML snippet
Impact:    Why it matters for ranking/indexing/UX
Fix:       Clear implementation step
```

**Confidence Labels:**
| Label | Meaning |
|-------|---------|
| `Confirmed` | Directly observed in page source or script output |
| `Likely` | Strong signal, indirect evidence |
| `Hypothesis` | Possible but unconfirmed (e.g., script failed) |

**Severity Levels:**
| Level | Meaning |
|-------|---------|
| 🔴 Critical | Directly impacts rankings or indexing |
| ⚠️ Warning | Optimization opportunity |
| ✅ Pass | Meets or exceeds standards |
| ℹ️ Info | Not applicable or informational |

### Scoring Configuration

**File:** `resources/config/scoring.json`

Defines category weights for the overall SEO Health Score:

| Category | Weight |
|----------|--------|
| Technical SEO | 25% |
| Content Quality | 20% |
| On-Page SEO | 15% |
| Schema / Structured Data | 15% |
| Performance (CWV) | 10% |
| Image Optimization | 10% |
| AI Search Readiness (GEO) | 5% |

### Freshness Tracking

Every reference file has a `<!-- Updated: YYYY-MM-DD -->` comment. CI runs `scripts/reference_freshness.py` to flag files older than 90 days.

---

## 7. End-to-End Data Flow

### Tracing Your Wikipedia Audit

Here is exactly what happened when you ran the audit for `https://en.wikipedia.org/wiki/Wikipedia`:

```
Phase 1: TRIGGER
─────────────────
You typed: "Run SEO audit on https://en.wikipedia.org/wiki/Wikipedia"
The LLM read SKILL.md → matched "seo audit" → loaded seo-audit.md
Single URL was detected → fell back to seo-page.md

Phase 2: EVIDENCE COLLECTION
────────────────────────────
Step A: LLM ran read_url_content("https://en.wikipedia.org/wiki/Wikipedia")
        → returned the full HTML of the page

Step B: LLM ran Python scripts:
  python3 fetch_page.py "https://en.wikipedia.org/wiki/Wikipedia" --output /tmp/page.html
  python3 parse_html.py /tmp/page.html --url "..." --json
  python3 social_meta.py "https://en.wikipedia.org/wiki/Wikipedia"
  python3 sitemap_checker.py "https://en.wikipedia.org/wiki/Wikipedia"
  python3 robots_checker.py "https://en.wikipedia.org/wiki/Wikipedia"
  python3 readability.py /tmp/page.html --json
  python3 image_inventory.py /tmp/page.html --json
  python3 validate_schema.py /tmp/page.html --json
  python3 redirect_checker.py "https://en.wikipedia.org/wiki/Wikipedia"
  python3 security_headers.py "https://en.wikipedia.org/wiki/Wikipedia"

Each script returned structured JSON evidence.

Phase 3: LLM ANALYSIS
──────────────────────
The LLM (acting as SEO analyst) synthesized:
- Script outputs (structured data from each check)
- Its own read_url_content results (page text, structure)
- Reference knowledge (CWV thresholds, E-E-A-T rules, rubric)

For each finding, the LLM applied the rubric:
  Finding: "Meta description is missing"
  Evidence: "No <meta name='description'> tag in <head>"
  Impact: "Medium for most sites; Low for Wikipedia (Google uses lead paragraph)"
  Fix: "Add a 150-160 character meta description"

Confidence was labeled: "Confirmed" (directly observed in HTML)
Severity was labeled: "Warning" (not critical for Wikipedia specifically)

Phase 4: SCORING
─────────────────
The LLM scored each category per the scoring.json weights:
  Technical:    9/10  (HSTS, canonical, clean URL — minor cache issue)
  On-Page:      8/10  (missing meta desc, heading order)
  Content:     10/10  (29,700 words, 588 references, 4,110 links)
  Schema:       8/10  (valid Article JSON-LD, missing OG/Twitter)
  Performance:  6/10  (1.36 MB HTML, no lazy loading)
  Images:       6/10  (40% missing/empty alt text)
  Intl SEO:     6/10  (319 interlanguage links, no formal hreflang)

Weighted overall: 8.5/10

Phase 5: DELIVERY
──────────────────
The LLM wrote the markdown report you received, structured per the rubric:
1. Executive Summary
2. Technical SEO (table per check)
3. On-Page SEO (title, meta, headings, content depth)
4. Structured Data (JSON-LD, OG, Twitter)
5. International SEO
6. Images & Media
7. Links & Authority
8. Mobile & UX
9. Performance
10. Crawlability & Index Control
11. Priority Recommendations
12. Scorecard
13. Context notes
```

### Key Insight: What the LLM Did vs. What Scripts Did

| Check | How it was determined |
|-------|----------------------|
| HTTP 200, canonical, charset | Script: `fetch_page.py` + `parse_html.py` |
| Title tag "Wikipedia - Wikipedia" | LLM: `read_url_content` (confirmed by script) |
| Meta description missing | LLM: `read_url_content` (confirmed by script) |
| 68 headings, H2 before H1 | Script: `parse_html.py` tree output |
| 29,700 words, 588 references | LLM: counted via reading + analysis |
| 45 images, 13 missing alt | Script: `image_inventory.py` |
| Article JSON-LD with Q52 sameAs | Script: `validate_schema.py` |
| "Low impact for Wikipedia" | **LLM judgment**, not from any script |
| Priority ordering | **LLM reasoning** based on impact × effort |

The scripts provide **data**. The LLM provides **judgment**.

---

## 8. Customization Guide

### How to Add a New SEO Check

1. **Edit the sub-skill file** (`resources/skills/seo-page.md`):
   ```markdown
   ## New Check
   - Verify that `X-Custom-Header` is present
   - Flag if value is older than 30 days
   ```

2. **(Optional) Add a Python script** (`scripts/`):
   ```python
   """
   Check for X-Custom-Header freshness.
   Usage: python scripts/custom_check.py <url>
   """
   ```

3. **Update the rubric** if needed (`resources/references/llm-audit-rubric.md`)

4. **Update scoring config** (`resources/config/scoring.json`) if your check affects a category weight

### How to Change the Output Format

- **Report structure:** Edit `resources/references/llm-audit-rubric.md` (the "Output Contract" section)
- **HTML dashboard:** Edit `scripts/generate_report.py` (the `generate_html` function)
- **Scoring:** Edit `resources/config/scoring.json` (category weights)

### How to Port to a Different Platform

The `install.sh` / `install.ps1` scripts handle platform-specific installation:

| Platform | Install target | Files written |
|----------|---------------|---------------|
| Claude Code | `~/.claude/skills/seo/` | SKILL.md + resources + scripts |
| Windsurf | `.windsurf/rules/seo.md` + `.windsurf/skills/seo/` | Rule file + skill assets |
| Cursor | `.cursor/rules/seo.mdc` + `.cursor/skills/seo/` | MDC rule + skill assets |
| Copilot | `.github/copilot-instructions.md` + `.github/skills/seo/` | Instructions + assets |

Each platform has its own skill/rules format, but the **core content is identical** — only the wrapper file format changes.

### How to Create a Minimal Custom Version

For a simplified version with just the checks you need:

```
my-custom-seo-skill/
├── SKILL.md                          # Orchestrator (your workflow)
├── resources/
│   ├── skills/
│   │   └── seo-page.md               # Your checks only
│   └── references/
│       ├── llm-audit-rubric.md       # Your rubric
│       └── quality-gates.md          # Your thresholds
└── scripts/
    ├── fetch_page.py                 # From upstream
    ├── parse_html.py                 # From upstream
    └── your-custom-script.py         # Your addition
```

The SKILL.md file is the only mandatory file — everything else is optional and loaded on demand.

---

## Appendix: File Reference

### Complete File Tree (Key Files)

```
Agentic-SEO-Skill/
├── SKILL.md                              # Master orchestrator (369 lines)
├── install.sh                            # Linux/macOS installer
├── install.ps1                           # Windows installer
├── requirements.txt                      # Python deps
├── pyproject.toml                        # Project metadata
├── .env.example                          # API key template
├── resources/
│   ├── skills/                           # 16 sub-skill files
│   │   ├── seo-page.md                   #   Single-page audit
│   │   ├── seo-audit.md                  #   Full-site audit
│   │   ├── seo-technical.md              #   Technical SEO
│   │   ├── seo-content.md                #   Content quality
│   │   ├── seo-schema.md                 #   Schema markup
│   │   ├── seo-sitemap.md                #   Sitemap analysis
│   │   ├── seo-images.md                 #   Image optimization
│   │   ├── seo-geo.md                    #   GEO
│   │   ├── seo-aeo.md                    #   AEO
│   │   ├── seo-links.md                  #   Link profile
│   │   ├── seo-programmatic.md           #   Programmatic SEO
│   │   ├── seo-competitor-pages.md       #   Competitor pages
│   │   ├── seo-hreflang.md               #   International SEO
│   │   ├── seo-plan.md                   #   Strategic planning
│   │   ├── seo-article.md                #   Article analysis
│   │   └── seo-github.md                 #   GitHub SEO
│   ├── agents/                           # 10 specialist agents
│   │   ├── seo-technical.md
│   │   ├── seo-content.md
│   │   ├── seo-performance.md
│   │   ├── seo-schema.md
│   │   ├── seo-sitemap.md
│   │   ├── seo-visual.md
│   │   ├── seo-verifier.md
│   │   └── seo-github-*.md
│   ├── references/                       # 10 reference files
│   │   ├── llm-audit-rubric.md           #   Universal rubric
│   │   ├── cwv-thresholds.md             #   Core Web Vitals
│   │   ├── eeat-framework.md             #   E-E-A-T scoring
│   │   ├── quality-gates.md              #   Content minimums
│   │   ├── schema-types.md               #   Schema.org types
│   │   └── google-seo-reference.md       #   Google reference
│   ├── config/
│   │   └── scoring.json                  # Category weights
│   ├── schema/
│   │   └── templates.json               # Pre-built JSON-LD templates
│   └── templates/                        # Industry strategy templates
│       ├── saas.md
│       ├── ecommerce.md
│       ├── local-service.md
│       ├── publisher.md
│       ├── agency.md
│       └── generic.md
├── scripts/                              # 89 Python + 2 shell scripts
│   ├── audit_runner.py                  # Main CLI entry point
│   ├── fetch_page.py                    # HTTP fetcher
│   ├── parse_html.py                    # HTML → SEO elements
│   ├── generate_report.py               # HTML dashboard (1766 lines)
│   ├── finding_verifier.py             # Dedup/validation
│   └── ...                              # 84 more
├── tests/
├── wiki/
└── docs/
    └── images/
```
