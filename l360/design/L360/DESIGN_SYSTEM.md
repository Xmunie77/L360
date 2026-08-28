# Learning 360° Foundation — Design System

**v2.0 · 27 August 2026** · for the booking & payment system

Learning 360° Foundation is a Malta-based inclusive education provider (Swatar) offering
early intervention, literacy support, study skills, exam coaching, and coaching for teens
and parents. Founded by Francesca Diacono, Justine Balani and Samantha Pace. Its audience
is parents of neurodivergent children, teenagers, adult learners and educators.

**That audience is the design constraint.** Every rule below that looks fussy —
contrast floors, no justified text, no countdown timers, no colour-only status — exists
because the people using this product include dyslexic, autistic and ADHD users, and the
organisation's whole proposition is that it does inclusion properly.

---

## How to use this file

- `tokens.css` is the source of truth for values. Import it once; never hardcode a hex,
  font size, radius or spacing value anywhere else.
- `tokens.json` is the same set for JS/Tailwind config or design tools.
- `BOOKING_PAYMENT_SPEC.md` covers the flows, components and copy for this product.
- Anything labelled **[EXTRACTED]** came from the live site's compiled stylesheet and
  served assets. Anything labelled **[ADDED]** is new and needs founder sign-off.
- Where a rule says MUST, treat it as a build blocker.

---

## 1. Brand assets

| Asset | File | Notes |
|---|---|---|
| Primary lockup | `learning360-logo-white.png` | 406×104, white, transparent |
| Mark | `learning360-mark-orange.png` | 512×512, orange, transparent |

The mark is a hexagon opened along its vertical axis holding an abstract figure — head,
shoulders, base. The learner sits *inside* the shape. 360° means a full circle drawn
around one person, which is also the site's own explanation of the name.

**Rules**

- The name is **Learning 360° Foundation** on first mention, **Learning 360°** after.
  The degree sign is part of the wordmark. Never "L360" in anything user-facing.
- White lockup on `--l360-ink`, `--l360-dgrey`, orange, or photography.
  Orange mark on white or ink only.
- Clear space: the height of the central figure on all four sides. **[ADDED]**
- Minimum size: lockup 140px wide, mark alone 24px. **[ADDED]**
- MUST NOT recolour the figure, add strokes, stretch, or rotate the hexagon.

⚠️ **No vector master is publicly available.** Only PNGs are served by the site. Request
the SVG/AI files from **Lo&Behold**, the studio credited in the site footer, before any
print work or before rendering the mark above ~200px. Until then, use the 512px mark and
do not upscale.

---

## 2. Colour

### 2.1 The rule that changes everything

> **Brand orange `#FE9345` is a FILL, not an ink.**
> It scores 2.22:1 on white — it fails WCAG AA for text at every size.
> White on orange is also 2.22:1, so white-label buttons fail too.

The live website currently sets orange type on light grounds in several places. Do not
carry that over. The fixed system:

| Need | Token | Value | Ratio |
|---|---|---|---|
| Orange as a background | `--l360-orange` | `#FE9345` | ink label on it = **7.35:1** ✅ AAA |
| Orange as text / links / icons on light | `--l360-orange-deep` | `#AD4900` | **5.63:1** ✅ AA |
| Orange as text on the ink ground | `--l360-orange` | `#FE9345` | **7.35:1** ✅ AAA |
| Selected / hover ground on light | `--l360-orange-tint` | `#FFF1E6` | ink on it = 14.72:1 ✅ |

`--l360-orange-deep` is hue-locked to the brand orange (both sit at ~25° hue), so it reads
as the same colour family, just usable.

### 2.2 Full palette

| Token | Value | Source | Use |
|---|---|---|---|
| `--l360-orange` | `#FE9345` | [EXTRACTED] | Primary CTA fill, active states, brand moments |
| `--l360-orange-deep` | `#AD4900` | [ADDED] | Links, orange text, icons on light |
| `--l360-orange-tint` | `#FFF1E6` | [ADDED] | Selected slot ground, hover rows |
| `--l360-ink` | `#202020` | [EXTRACTED] | Body text (16.29:1), dark sections |
| `--l360-dgrey` | `#373737` | [EXTRACTED] | Raised surfaces on dark |
| `--l360-bgrey` | `#424242` | [EXTRACTED] | Secondary body copy (10.05:1) |
| `--l360-lgrey` | `#E0E0E0` | [EXTRACTED] | Hairlines, input borders |
| `--l360-mute` | `#6E6E6E` | [ADDED] | Captions, hints, metadata (5.10:1) |
| `--l360-disabled` | `#969696` | [EXTRACTED] | **Disabled controls only.** Was the site's caption grey at 2.96:1 — it fails AA and MUST NOT carry readable text |
| `--l360-white` | `#FFFFFF` | [EXTRACTED] | Page ground |

### 2.3 State colours **[ADDED]**

Payments need unambiguous states, and the brand has none.

| State | Text | Ground | Ratio (text on ground) |
|---|---|---|---|
| Success / paid | `--l360-success` `#0F7A4A` | `--l360-success-bg` `#E8F5EE` | 4.80:1 ✅ |
| Error / failed | `--l360-danger` `#B3261E` | `--l360-danger-bg` `#FDECEA` | 5.72:1 ✅ |
| Info | `--l360-info` `#1B5E9C` | `--l360-info-bg` `#E7F0F8` | 5.82:1 ✅ |
| Pending / awaiting | `--l360-pending` `#5F5F5F` | `--l360-pending-bg` `#F1F1F1` | 6.39:1 on white ✅ |

**There is deliberately no amber "warning" colour.** Amber is visually identical to the
brand orange, and if warnings are amber then orange stops meaning "this is the action to
take". Anything that would have been a warning is either **info** (blue) or **pending**
(neutral). Orange is reserved for brand and primary action, full stop.

**Colour MUST NEVER be the only signal.** Every status carries a text label; every error
carries an icon and words. Test the whole flow in greyscale before shipping.

### 2.4 Focus

- `outline: 3px solid var(--l360-focus-ring); outline-offset: 2px;`
- Focus ring is `#AD4900` on light and `#FFFFFF` on the dark ground.
- MUST be visible on every interactive element, including calendar cells and slot buttons.
- MUST NOT be removed on mouse click — no `:focus { outline: none }`.

---

## 3. Type

**Work Sans**, weights 300/400/500/600/700. One family, no second face. [EXTRACTED]

| Token | Size / line | Role |
|---|---|---|
| `t1` | 50 / 60 | Page hero only |
| `t2` | 40 / 45 | Section heading |
| `t3` | 30 / 35 | Step heading, price total |
| `t4` | 22 / 28 | Sub-heading |
| `t5` | 20 / 25 | Card title |
| `t6` | 18 / 25 | Intro paragraph (weight 300) |
| `t7` | 16 / 22 | **Body default** (weight 400) |
| `t8` | 14 / 22 | Caption, hint, table cell |

Under 820px, `t1` steps down to `t2` and `t2` to `t3`.

### Setting rules — MUST

- Body text MUST NOT go below 16px anywhere, including on mobile and in form fields
  (under 16px, iOS zooms on focus).
- Left aligned, ragged right. **Justified text is banned** — the rivers it creates cost
  dyslexic readers comprehension.
- Line length 60–70 characters. Form column caps at `--l360-maxw-form` (560px).
- Sentence case. Uppercase only in the eyebrow style (11px / 0.14em tracking).
- **Bold for emphasis, never italic.** Italics are harder for many dyslexic readers.
- Short paragraphs, one idea each, separated by space not indents.
- Amounts and booking references set in `--l360-font-mono` so digits align in tables.

---

## 4. Shape, space, layout

| | Value | Use |
|---|---|---|
| `--l360-r-sm` | 4px | Inputs, tags, chips [EXTRACTED] |
| `--l360-r-md` | 8px | Cards, panels, modals [EXTRACTED] |
| `--l360-r-full` | pill | Buttons, badges, avatars [EXTRACTED] |

Spacing scale (4pt): 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96. Nothing off-scale. **[ADDED]**

Layout: 1080px max content, 560px max for booking/payment column, 24px gutters,
28px page padding (20px under 640px), single breakpoint at 820px. **[ADDED]**

---

## 5. Core components

### Button

Pill, weight 600, `--l360-t7`, min height 44px, horizontal padding 30px.

| Variant | Light ground | Dark ground |
|---|---|---|
| Primary | Orange fill, **ink label** | Orange fill, ink label |
| Secondary | Transparent, 2px ink border, ink label | Transparent, 2px white border, white label |
| Destructive | Transparent, 2px `--l360-danger` border, danger label | — |
| Disabled | `--l360-lgrey` fill, `--l360-disabled` label, `aria-disabled` | — |

- Hover on primary: invert to ink fill / white label.
- MUST NOT use white-on-orange labels (2.22:1).
- One primary button per screen.
- Labels name the action and keep that name through the flow: the button that says
  **Pay €45** produces a screen that says **Paid**. Never "Submit".
- Loading state: label changes to a present participle (**Paying…**), button stays the
  same width, `aria-busy="true"`, and MUST become non-repeatable to prevent double charge.

### Input

Label always visible above the field. Placeholder-only labelling is banned — it vanishes
the moment someone types, which is exactly the wrong behaviour for a working-memory
difficulty.

- 16px text, 12px/14px padding, `--l360-r-sm`, 1px `--l360-lgrey` border.
- Focus: `--l360-orange-deep` border + 3px halo.
- Error: `--l360-danger` border + message below with an icon, tied by `aria-describedby`.
- Hint text in `--l360-mute` **below** the label, not inside the field.
- Real `<label for>`, real `autocomplete` attributes, real input types.

### Card

`--l360-r-md`, 1px `--l360-lgrey`, 20px padding. Optional media header on `--l360-dgrey`.
Eyebrow (orange-deep, uppercase 11px) → title `t5`/600 → body `t8` in `--l360-bgrey`.

### Status badge

Pill, 11px uppercase 600, 4px/10px padding, tinted ground + matching state text.
Always carries a word, never colour alone.

---

## 6. Accessibility floor — non-negotiable

The organisation sells inclusion. Shipping an inaccessible booking flow is a brand failure
before it is a technical one.

- WCAG 2.1 **AA minimum**, AAA on body text where achievable.
- Keyboard: every flow completable without a mouse, including the date picker.
- Visible focus everywhere; logical tab order; skip link to main content.
- Hit targets ≥ 44px; time-slot buttons ≥ 48px.
- `prefers-reduced-motion` respected — no parallax, no auto-carousels, no motion on
  step transitions.
- Screen readers: live region announcements when slot availability changes or a payment
  result arrives (`aria-live="polite"`, `assertive` for errors).
- Forms: errors listed at the top of the form AND inline; never on a colour cue alone.
- **No countdown pressure.** See `BOOKING_PAYMENT_SPEC.md` §6 — this is a deliberate
  divergence from typical booking UX and it is intentional.
- Test with 200% zoom and with Windows High Contrast Mode.

---

## 7. Voice

The foundation's own writing is warm, plain and specific about what happens in a session.
Match it.

**Do**
- Say what happens: "we work on note-taking and self-testing".
- "You" for the reader, "we" for the foundation.
- Lead with the learner, then the family, then the school.
- Sentences under ~20 words.
- British English: programme, organisation, personalised, enrolment.

**Don't**
- "Holistic synergies", "bespoke solutions", "unlock potential" as a bare claim.
- Deficit framing: "suffers from", "low-functioning", "special needs child".
- Pity or hero narratives about children.
- Clinical distance: "the client presents with…".
- Exclamation marks in transactional copy. A payment receipt is not excited.

**Errors explain and instruct; they do not apologise.** "That card was declined. Try
another card, or pay by bank transfer." Not "Oops! Something went wrong 😔".

⚠️ The live site mixes British and US spellings (`personalized`, `organized`). Standardise
on British throughout the new system.

---

## 8. Open items — confirm before launch

| # | Item | Owner |
|---|---|---|
| 1 | Vector logo master (SVG/EPS) | Lo&Behold / founders |
| 2 | Sign-off on all **[ADDED]** tokens, especially `--l360-orange-deep` | Founders |
| 3 | Whether the marketing site will also be corrected for the orange-on-white contrast failure, or whether the booking system diverges | Founders |
| 4 | Work Sans licensing for any print/app use (it is open-source via Google Fonts — verify the current licence terms for your use) | Dev |
| 5 | Everything in `BOOKING_PAYMENT_SPEC.md` §9 (legal entity details, data protection) | Founders + lawyer |
