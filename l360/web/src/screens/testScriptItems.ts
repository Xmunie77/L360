// Founder test-script content — TEMPORARY (delete with TestScript.tsx,
// routers/test_script.py and migration 0022 when testing wraps).
// `do_` is the action, `expect` what correct behaviour looks like. Item
// ids are stable: marks in the DB are keyed on them, so reword freely
// but never reuse an id for a different check.

export interface TestItem {
  id: string;
  do_: string;
  expect: string;
}

export interface TestSection {
  key: string;
  title: string;
  items: TestItem[];
}

export const TEST_SECTIONS: TestSection[] = [
  {
    key: "A · GETTING IN",
    title: "Sign-in, phone install, views",
    items: [
      { id: "a1", do_: "Sign in on your laptop.", expect: "You land on the Admin page; the menu shows Calendar, Sessions, Learners, Educators, Finance, Admin, Profile; the orange L360 mark sits top-right." },
      { id: "a2", do_: "On your phone, open the installed app (Safari → Share → Add to Home Screen if you haven't).", expect: "Full screen, no browser bars; the menu is a ☰ drawer from the left; the page title sits centred between ☰ and the logo, clear of the iPhone clock." },
      { id: "a3", do_: "Profile → \"Viewing as\" → Educator. Look around, then switch back to Admin.", expect: "As Educator the menu shrinks to Calendar / Sessions / Finance / Profile (plus this Test script), Sessions shows only your own, Finance is just your monthly summary. Switching back restores everything." },
      { id: "a4", do_: "Profile → change your password, sign out, sign back in with the new one.", expect: "The old password stops working immediately." },
    ],
  },
  {
    key: "B · CALENDAR",
    title: "Views & booking",
    items: [
      { id: "b1", do_: "Calendar, Day + Rooms, on today.", expect: "One column per room; a thin red line marks the current time on today." },
      { id: "b2", do_: "Tap an empty slot once. Tap a different spot. Then tap the orange band itself.", expect: "First tap: an orange band appears reading e.g. \"10:15 — tap to book\". Tapping elsewhere just moves it. Tapping the band opens the booking form at that exact time. Works the same with a mouse and a thumb." },
      { id: "b3", do_: "Book a TEST session for tomorrow: educator = you, learner = your TEST family, any session type.", expect: "It appears on the grid, and a \"Booking confirmed\" email reaches your test address (give it a minute; check spam)." },
      { id: "b4", do_: "Try booking the same room at an overlapping time.", expect: "Refused with \"already booked\" — double-booking is impossible." },
      { id: "b5", do_: "Switch to Week + Rooms. Try \"All rooms\", then a single room from the Showing picker.", expect: "Seven day-columns, Monday first. All rooms packs every room's sessions side by side (room named on each block); a single room shows just its own." },
      { id: "b6", do_: "Week + Educators, pick yourself. Then look at the same view on your phone.", expect: "Your week on the laptop as a grid; on the phone the week becomes a day-by-day list you scroll, each session tappable." },
      { id: "b7", do_: "Use ‹ › and Today; then try the \"Next available\" strip's Book button.", expect: "Arrows step a day (or a whole week in Week view); Today snaps back; Book opens the form pre-filled with the suggested room and time." },
    ],
  },
  {
    key: "C · SESSIONS",
    title: "Outcomes & the confirm flow",
    items: [
      { id: "c1", do_: "Open the Sessions tab.", expect: "An Upcoming / Past / Cancelled selector; Upcoming is the default, soonest first. Dates read like 05/09/26 10:00." },
      { id: "c2", do_: "Switch to Past.", expect: "Most recent first; every session carries two pills — Status (e.g. Delivered) and Billing (e.g. To bill). On the phone these are cards, not a sideways-scrolling table." },
      { id: "c3", do_: "Book a TEST session for earlier today, then Confirm it: it took place → Delivered.", expect: "You're offered \"Send invoice — €xx\" for that single session, or \"Not now — monthly run\". Choose Not now; billing shows To bill." },
      { id: "c4", do_: "Confirm the same session again: No show → don't charge → pick a reason (e.g. Child ill).", expect: "Pills change to No show · Fee waived; the reason is kept." },
      { id: "c5", do_: "Flip to Educator view (Profile) and look at that waived session; flip back.", expect: "As an educator the waived fee is final — no way to re-charge. As admin you can still revisit it." },
      { id: "c6", do_: "Cancel an upcoming TEST session (more than a day away).", expect: "It asks \"Cancel this session?\" first — Yes, cancel / Keep it. It then shows under the Cancelled filter, and a cancellation email goes out." },
      { id: "c7", do_: "Book a TEST session within the next 24 hours, then cancel it.", expect: "Because it's inside 24 hours it asks whether the family should still be charged (late cancellation), with a reason if you waive." },
    ],
  },
  {
    key: "D · LEARNERS",
    title: "Families & onboarding",
    items: [
      { id: "d1", do_: "Learners → search for a family three ways: by parent surname, by the learner's name, and by an educator's name.", expect: "All three find the right rows; long educator lists show \"…, +2\" instead of stretching the table." },
      { id: "d2", do_: "Add learner (opens a modal): first try submitting empty, then fill it in — watch the date-of-birth field. Use TEST + your email.", expect: "Empty submit marks each missing field in red under the field itself. Typing a date of birth shows a live Age N box beside it." },
      { id: "d3", do_: "Open your TEST family from the list.", expect: "The page has just a ‹ Back button up top. Details open LOCKED with \"Unlock to edit\" right at the top; on a laptop the fields sit in tidy pairs filling the card." },
      { id: "d4", do_: "Unlock, change something, Save.", expect: "\"Saved.\" appears next to the Save button (not off-screen at the top). Cancel instead of Save restores the old values." },
      { id: "d5", do_: "Send the onboarding form, open the email as a parent would, and submit it — try skipping a required consent first.", expect: "The form refuses until every required agreement is ticked; after submitting, the learner's record shows everything you typed and the badge reads Submitted." },
      { id: "d6", do_: "Back in the list, Deactivate your TEST family.", expect: "The button first turns red asking \"Really deactivate?\" — nothing happens on one tap. After confirming, the family shows Inactive but isn't destroyed." },
    ],
  },
  {
    key: "E · EDUCATORS",
    title: "Staff profiles & HR",
    items: [
      { id: "e1", do_: "Educators tab → tap a colleague's name.", expect: "A wide profile card: photo, role & level, bio as readable text (no edit boxes until you ask for them)." },
      { id: "e2", do_: "Open YOUR own profile: check photo and bio, then Edit bio, change a word, Cancel; edit again and Save.", expect: "Cancel restores the old wording exactly; Save keeps the change. The consent line under the photo shows when consent was recorded." },
      { id: "e3", do_: "Scroll to \"HR details — Admins only\" on your own profile.", expect: "Your IBAN, ID card, address and the rest are correct (imported from your invoices and the POMA sheet). Note anything wrong or missing in the Problem box — that's exactly what this check is for." },
      { id: "e4", do_: "Flip to Educator view and check what an educator can see.", expect: "Educators have no Educators / Learners / Admin tabs at all, and HR details are nowhere — they exist only for admins." },
      { id: "e5", do_: "Add staff member with everything left empty.", expect: "Each missing field is marked individually (email, full name, password of at least 8 characters)." },
    ],
  },
  {
    key: "F · FINANCE",
    title: "Billing, invoices, bank",
    items: [
      { id: "f1", do_: "Finance → it opens on Billing. Check the dates, then Run billing.", expect: "The period defaults to the 1st of this month → today. The result lists each drafted invoice by family with its total — your TEST family among them (from the Delivered session in C)." },
      { id: "f2", do_: "Invoices pill → tap your TEST family's draft → Issue invoice.", expect: "It asks first, telling you it will number the invoice and email that named family; after \"Issue & email\" a message stays on screen: \"Invoice L360-2026-00xx issued and emailed to …\". The email (with PDF) lands at your test address." },
      { id: "f3", do_: "Download the invoice PDF from the same screen.", expect: "Letterhead, bank details and totals match our invoice layout, and every line names the educator." },
      { id: "f4", do_: "Void / amend the test invoice.", expect: "The number is kept (never reused) and the sessions on it unlock so they can be re-billed." },
      { id: "f5", do_: "Re-issue a TEST invoice, then Bank pill → Record payment: pick it and deliberately type MORE than it's worth.", expect: "The invoice picker shows how much is due (e.g. €35.00 due); over-paying is refused with the ceiling spelled out." },
      { id: "f6", do_: "Record a correct CASH payment for part of it.", expect: "Cash demands a \"Received by\" person; afterwards the invoice shows Partially paid with the right balance." },
      { id: "f7", do_: "Statements pill: your monthly summary, and your TEST family's statement.", expect: "Your summary shows delivered sessions at your pay rate with a total; the family statement shows the invoice and the cash payment with a correct closing balance." },
    ],
  },
  {
    key: "G · ADMIN",
    title: "Settings & templates",
    items: [
      { id: "g1", do_: "Admin → Rooms: add a TEST room, edit its name, then Deactivate it. Scroll down.", expect: "Deactivate is the same two-step red confirm; the Room utilisation report sits below the room list." },
      { id: "g2", do_: "Educator levels and Services Price List.", expect: "Every level's rates and every named service's family price / tutor pay match what we actually charge — read them properly, this is the money table." },
      { id: "g3", do_: "Email tab → Automated emails → open \"Session reminder\": change a word, press Escape; then edit again, Save; then Reset to default.", expect: "Escape with unsaved changes asks \"Discard your unsaved changes?\". Saving shows a Customised badge in the list. Reset asks \"Really reset?\" and then shows the restored wording without closing." },
      { id: "g4", do_: "Invoice template: tweak the footer text, Save, then View sample invoice.", expect: "The sample PDF shows your new footer. (Put it back afterwards.)" },
    ],
  },
  {
    key: "H · WRAP UP",
    title: "Cleanup",
    items: [
      { id: "h1", do_: "Cancel any TEST sessions still upcoming; deactivate your TEST family and TEST room if you haven't.", expect: "Test invoices stay — numbers are never reused, so they remain as a record. That's fine." },
      { id: "h2", do_: "Last look: anything anywhere that felt confusing, slow, or wrongly worded — even if it \"worked\"?", expect: "Flag this item and write it down. Confusion counts as a bug." },
    ],
  },
];

export const TEST_ITEM_COUNT = TEST_SECTIONS.reduce((n, s) => n + s.items.length, 0);
