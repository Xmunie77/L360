# Learning 360° — Booking & Payment System

**Spec v1.0 · 27 August 2026** · read `DESIGN_SYSTEM.md` and import `tokens.css` first.

Everything here is **[PROPOSED]**. It is a design and UX specification derived from what
the foundation publicly offers; it has not been confirmed against their actual operating
model, pricing, or legal setup. Validate §1 and §9 with the founders before building.

---

## 1. What is being booked — confirm this first

The site lists these services, which do not all book the same way:

| Service | Likely booking shape |
|---|---|
| Early intervention | Assessment first, then a recurring weekly programme |
| Literacy support | Recurring individual sessions |
| Organisational & study skills | Recurring individual sessions |
| Exam coaching / examination techniques | Block of sessions before an exam date |
| Coaching for teens / for parents | Individual sessions, possibly ad hoc |
| Group skill sessions | Fixed-cohort enrolment, ad hoc availability |
| Creative writing | Cohort or block |
| Training & workshops for educators | B2B — invoiced, quoted, often no card payment |
| Inclusion & diversity training | B2B — invoiced |

**This means the system needs three distinct paths, not one:**

1. **Enquiry → consultation** (the site's own process starts with contact, then an online
   meeting, then an initial session). Most new families should land here, not in a
   checkout.
2. **Recurring programme** for existing families — a repeating weekly slot, paid monthly
   or in blocks of sessions.
3. **B2B request** for schools and employers — a quote request, then an invoice. **No
   card checkout for this path.**

> ⚠️ Do not build a single "pick a slot, pay now" funnel. The foundation's published
> process is Contact → Initial online meeting → Initial session → Programme design →
> Regular sessions → Ongoing supervision → Review meeting. A cold card checkout for a
> first early-intervention session would contradict how they actually work. Confirm.

---

## 2. Booking states

```
enquiry ─→ consultation_booked ─→ programme_proposed ─→ active
                                                          │
slot: available ─→ held ─→ awaiting_payment ─→ confirmed ─→ attended
                    │             │                │
                    └─ released   └─ payment_failed└─→ cancelled ─→ refunded
                                                   └─→ rescheduled
                                                   └─→ no_show
```

Each state maps to one badge:

| State | Badge label | Tokens |
|---|---|---|
| `held` | Holding your slot | pending |
| `awaiting_payment` | Payment needed | pending |
| `confirmed` | Confirmed | success |
| `attended` | Attended | success |
| `payment_failed` | Payment failed | danger |
| `cancelled` | Cancelled | pending |
| `refunded` | Refunded | info |
| `rescheduled` | Moved | info |
| `no_show` | Missed | pending — **never** danger; a missed session is not an error, and families with a disabled child miss appointments for reasons that do not deserve a red badge |

---

## 3. Screens

### 3.1 Service selection
Card grid, one card per service, using the standard service card. Each card states: who
it is for, session length, whether it is one-to-one or group, and whether it starts with
a consultation. Price shown only where a fixed price genuinely exists; otherwise
"Priced after your consultation" — not "From €—".

### 3.2 Educator selection (optional step)
Shows name, role, one-line specialism, photo. Default option: **"No preference — match
me"**, listed first and pre-selected. Many families do not know who to pick, and forcing
a choice adds anxiety with no benefit.

### 3.3 Date & time picker

The highest-risk component. Rules:

- Month grid + a **list** of times for the selected day. The list is a `<ul>` of buttons,
  not a grid — screen reader users should be able to read straight down.
- Calendar is a real `role="grid"` with arrow-key navigation, Home/End, PageUp/PageDown.
- Days with no availability are `aria-disabled`, visually `--l360-disabled`, and carry
  `title`/`aria-label` "No sessions available".
- Slot button: min height 48px, `--l360-r-full`, 1px `--l360-lgrey`.
  Selected = `--l360-orange-tint` ground, 2px `--l360-orange` border, ink text, plus a
  check icon and `aria-pressed="true"` — never colour alone.
- Times shown as `09:00 – 10:00` with the timezone stated once: **Malta time (CET/CEST)**.
- Dates as `Tuesday 3 March 2027` in full in headings, `03/03/2027` only in tables.
- When availability loads or changes, announce it: `aria-live="polite"` →
  "6 times available on Tuesday 3 March".
- Recurring bookings: pick the first session, then choose "every week" / "every fortnight"
  and an end date or number of sessions. Show the **full list of resulting dates** before
  payment, with the ability to drop individual dates. Never let someone pay for a series
  they have not seen.

### 3.4 Learner details

Collect the minimum. This form touches children's data and possibly health/disability
information — see §9.

Required: learner first name, learner last name, date of birth, parent/guardian name,
email, mobile.
Optional, clearly marked optional: school, year group, what you would like support with
(free text), anything that helps us make the session comfortable (free text).

- **Do not** build a checkbox list of diagnoses. A free-text box respects that families
  describe their child differently, and it avoids storing structured special-category
  data you may not need.
- Every optional field says "Optional" in the label, not just by absence of an asterisk.
- Save progress. A parent filling this in will be interrupted.

### 3.5 Summary & payment

Single column, 560px, in this order:

1. What you are booking — service, educator, all dates, duration
2. Price breakdown — per session × count, any discount, **total in bold `t3`**
3. Cancellation policy in plain words, visible **before** the pay button, not behind a link
4. Payment method
5. Consent checkboxes — unticked by default, each a separate box, each with its own label
6. Primary button: **Pay €180** — the actual amount in the label

Card fields are rendered by the payment provider (hosted fields / iframe), styled with
`tokens.css` values passed into the provider's appearance API. **Card numbers, CVC and
expiry MUST never touch your DOM, your logs, or your server.**

Offer at least one non-card route — bank transfer with an invoice — because some families
will not or cannot pay by card, and B2B clients will not.

### 3.6 Confirmation

- Heading: **Booked.** Then the essentials repeated: dates, times, address
  (Orange Grove, Block C, Triq l-Għabex, Swatar), who to contact.
- Booking reference in mono, large enough to read aloud on the phone.
- "Add to calendar" (.ics) — for many parents this is the single most useful control here.
- Confirmation email sent immediately, containing the same information. The email is the
  real receipt; the screen is a courtesy.
- What happens next, in one sentence, in their words: what to bring, whether to stay.

### 3.7 Manage a booking

Reschedule, cancel, view receipts, see remaining session credits. Reachable from a link in
every confirmation email — a magic link is kinder than a password for this audience.
Cancellation MUST be self-service and MUST NOT require a phone call.

---

## 4. Payment states and error copy

| Situation | Message |
|---|---|
| Declined | **That card was declined.** Your bank did not say why. Try another card, or pay by bank transfer. |
| Insufficient funds | **That card was declined.** Try another card, or pay by bank transfer. *(Do not surface "insufficient funds" — it may be read by someone standing next to the payer.)* |
| Expired card | **That card has expired.** Check the expiry date, or use another card. |
| 3-D Secure abandoned | **Your bank did not confirm the payment.** Your slot is still held. Try again, or choose bank transfer. |
| Network / timeout | **We could not reach the payment provider.** Nothing has been charged. Try again in a moment. |
| Already paid | **This booking is already paid.** Here is your receipt. |
| Refund issued | **Refunded €180.** It usually reaches your account in 5–10 working days — your bank sets the timing. |

Rules: state what happened, state whether money moved, state the next action. No emoji,
no apology, no error codes in the primary message (put the reference in small mono text
below for support).

**Double-charge protection is a design requirement, not just an engineering one:** the pay
button becomes non-repeatable on first press, and every payment request carries an
idempotency key.

---

## 5. Money formatting

- Currency: **EUR**, symbol before the amount, no space: `€45.00`.
- Always two decimals in totals and receipts.
- Mono font for amounts in tables so columns align.
- Never abbreviate in a payment context (`€1,200.00`, not `€1.2k`).
- Show the total in the button and in the summary. They must match to the cent.
- If a series is billed monthly, state the recurring amount, the date of the next charge,
  and how to stop it — on the same screen, before payment.

---

## 6. The countdown decision — read this before you disagree

Most booking systems hold a slot for 10 minutes with a visible ticking timer. **Do not do
that here.**

A visible countdown creates time pressure. For an anxious parent, an autistic adult, or
someone with ADHD filling in a form about their child, a shrinking timer is the single
most likely thing to make them abandon the booking — and this organisation exists to serve
exactly those people.

Instead:

- Hold the slot for **30 minutes**, server-side.
- Show a calm static line: *"This time is held for you while you finish."*
- At 25 minutes, offer — do not impose — an extension: *"Still there? We'll keep this time
  for another 30 minutes."* with a **Keep my time** button.
- If the hold does expire, do not lose their form data. Return them to the slot picker
  with everything else still filled in and a plain message: *"That time was released.
  Here are the next available times."*

This is a deliberate, defensible divergence from standard checkout UX. If someone asks why
conversion tactics are missing, this section is the answer.

---

## 7. Emails & documents

Four transactional templates, all plain and left-aligned, all readable at 16px, all with a
plain-text alternative:

1. **Booking confirmed** — dates, address, reference, add-to-calendar, cancel link
2. **Payment receipt** — itemised, foundation's legal name and registration details,
   reference
3. **Session reminder** — 24h before; one job only, no marketing
4. **Cancelled / refunded** — what was cancelled, what was refunded, when it arrives

No marketing content in transactional email. No tracking pixels in a message about a
child's therapy appointment.

Header: white lockup on `--l360-ink`. Body: white ground, ink text, orange used only for
the button fill. Email clients strip CSS variables — hardcode the hex values in email
templates and add a comment pointing back at `tokens.css`.

---

## 8. Component checklist for build

- [ ] Button — primary / secondary / destructive / disabled / loading
- [ ] Input, textarea, select — with label, hint, error, required/optional marking
- [ ] Checkbox and radio — 44px targets, label clickable
- [ ] Service card
- [ ] Educator card with "no preference" default
- [ ] Calendar grid (keyboard-navigable, `role="grid"`)
- [ ] Time-slot button — available / selected / unavailable
- [ ] Recurring-series builder with editable date list
- [ ] Order summary panel
- [ ] Payment method block (hosted fields wrapper)
- [ ] Status badge — 9 states from §2
- [ ] Alert / inline message — success / error / info / pending
- [ ] Modal — cancel, reschedule, extend hold (focus-trapped, Esc closes, returns focus)
- [ ] Stepper — shows all steps, allows going back without losing data
- [ ] Empty state — no availability, no bookings yet
- [ ] Skeleton / loading state — no spinner-only screens
- [ ] Receipt / invoice layout (print stylesheet, A4)

---

## 9. Legal and data — get answers before writing code

I cannot verify any of these and they materially change the build. Each needs a named
human to confirm.

| # | Question | Ask |
|---|---|---|
| 1 | **Legal entity details** required on invoices — registered name, registration number, registered address. | Founders |
| 2 | **Payment provider.** Needs to support Malta-registered entities, EUR, SCA/3-D Secure, and refunds. Availability, fees and features change — verify current terms directly with providers rather than relying on anything in this document. | Founders |
| 3 | **PCI DSS scope.** Using fully hosted payment fields normally keeps you in the lightest self-assessment tier, but the exact SAQ that applies depends on your integration. Confirm with your acquirer or provider — do not assume. | Provider / acquirer |
| 4 | **GDPR.** You will process children's personal data and probably information about disability or health, which is special-category data under Article 9 and needs a specific lawful basis and extra safeguards. Also required: privacy notice, retention schedule, DPA with every processor, and a decision on whether a DPIA is needed. | Lawyer / DPO |
| 5 | **Parental consent and who may book.** Can a 16-year-old book their own coaching session? Who can cancel? Separated parents? | Founders |
| 6 | **Cancellation and refund policy.** Notice period, late-cancellation charge, missed sessions, refunds on a paid block. Must be written before the checkout is designed — it is on the screen, not behind a link. | Founders |
| 7 | **Safeguarding.** Any child-protection requirements affecting what is recorded, who can see it, and how long it is kept. | Founders |
| 8 | **Existing systems.** Is there already a calendar, accounting package or CRM this must sync with? | Founders |

---

## 10. Build order

1. Import `tokens.css`. Build the primitives in §8 items 1–3 with the accessibility floor
   met from the first commit — retrofitting focus states and labels never happens.
2. Enquiry → consultation path. This is the real front door and probably the highest
   volume.
3. Manage-booking (reschedule/cancel) — before payment. Cancelling is a bigger relief for
   users than paying is a win for you, and it cuts admin phone calls immediately.
4. Payment, once §9 items 1–3 are answered.
5. Recurring series and session credits.
6. B2B quote/invoice path.

Ship 2 and 3 with manual invoicing behind them if §9 is still open. A working booking flow
with a bank-transfer instruction beats a blocked project waiting on legal sign-off.
