# Learning 360° — booking & payment system

Read this first. It tells you which files govern what.

## The project

A booking and payment system for **Learning 360° Foundation**, an inclusive-education
organisation in Swatar, Malta. They provide early intervention, literacy support, study
skills, exam coaching, and coaching for teens and parents. Founders: Francesca Diacono,
Justine Balani, Samantha Pace.

**Users are parents of neurodivergent children, teenagers, adult learners and educators.**
That is the design constraint behind most of the rules in these files. Where a rule looks
over-cautious, it is not — it is there because the organisation's entire proposition is
that it does inclusion properly, and an inaccessible booking flow would be a brand failure
before a technical one.

## Files and precedence

| File | Authority |
|---|---|
| `tokens.css` | **Source of truth for all values.** Import once. Never hardcode a hex, size, radius or spacing value anywhere else. |
| `tokens.json` | Same set for JS/Tailwind config or design tooling. Keep in sync with `tokens.css`. |
| `DESIGN_SYSTEM.md` | Brand, colour, type, shape, core components, accessibility floor, voice. |
| `BOOKING_PAYMENT_SPEC.md` | Flows, booking states, screens, payment copy, component checklist, build order. |
| `learning-360-design-system.html` | Visual preview for the founders. Not a build target — do not scrape values from it. |
| `learning360-logo-white.png` | Primary lockup, 406×104. |
| `learning360-mark-orange.png` | Mark, 512×512. |

If two files disagree, `tokens.css` wins on values and `BOOKING_PAYMENT_SPEC.md` wins on
behaviour.

## Confirmed vs proposed

- **[EXTRACTED]** — pulled from the live learning360.org.mt theme stylesheet and its served
  assets on 27 Aug 2026. This is the real brand. Do not change it.
- **[ADDED]** / **[PROPOSED]** — new, and not yet signed off by the founders. Build to it,
  but flag it as provisional in any handover, and expect the deep orange and the state
  palette in particular to be reviewed.

## Five rules that are easy to break by accident

1. **Brand orange `#FE9345` is a fill, never text on a light ground** (2.22:1, fails AA).
   For orange text or links on white, use `--l360-orange-deep` `#AD4900`. On the ink
   ground, plain brand orange is fine (7.35:1).
2. **No amber warning colour exists.** Amber reads as the brand orange. Anything that
   would be a warning is `info` (blue) or `pending` (neutral).
3. **Colour is never the only signal.** Every status carries a word. Check the flow in
   greyscale.
4. **No countdown timer on the slot hold.** 30-minute silent hold, offered extension, form
   data preserved on expiry. Reasoning in `BOOKING_PAYMENT_SPEC.md` §6 — read it before
   overriding, it is a deliberate divergence from standard checkout UX.
5. **Labels are always visible above fields.** No placeholder-only labelling anywhere.

## Blocked — do not build past these

`BOOKING_PAYMENT_SPEC.md` §9 lists the open questions for the founders and a lawyer. One of
them blocks real work:

- **GDPR.** The system processes children's data and probably disability information
  (special-category, Article 9). Lawful basis, retention, processor agreements and whether
  a DPIA is needed must be answered before any of that is stored.

Tax is deliberately out of scope for this spec — prices are displayed as given, with no VAT
line, breakdown or tax logic anywhere. Do not add one.

**You can still ship without the GDPR answers.** Build order is in §10: primitives →
enquiry flow → manage/cancel booking → payment. Only the steps that store learner details
depend on them.

## Ask rather than assume

Where the spec says "confirm with the founders", stop and surface it rather than picking a
default. The service model in `BOOKING_PAYMENT_SPEC.md` §1 in particular is inferred from
the public site, not confirmed — three distinct booking paths are proposed, and if that is
wrong the whole information architecture changes.
