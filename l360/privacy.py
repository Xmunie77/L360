"""The privacy notice served at /privacy — DRAFT pending legal review.

Linked from both public onboarding forms (client + educator). Server-
rendered plain HTML so it works without the SPA, loads instantly from an
email link, and is trivially printable. Content is deliberately factual —
what is collected, why, who processes it, what rights people have — and
clearly labelled as a draft until the Foundation's legal adviser signs it
off (the GDPR gate flagged in the original project spec and the 31/08
engineering review).

Wording changes: edit this file. Retention periods marked TBC need the
founders' decision before go-live.
"""

PRIVACY_HTML = """<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Privacy Notice — Learning 360° Foundation</title>
<style>
  body { font-family: "Work Sans", system-ui, sans-serif; line-height: 1.6; color: #232020;
         background: #FBFAF7; margin: 0; padding: 32px 18px 60px; }
  main { max-width: 720px; margin: 0 auto; }
  h1 { font-size: 1.6rem; } h2 { font-size: 1.1rem; margin-top: 28px; }
  .draft { background: #FBF3E5; border: 1px solid #EBD9B8; padding: 10px 14px; font-size: .92rem; }
  .muted { color: #6E6660; }
  ul { padding-left: 20px; } li { margin-bottom: 6px; }
</style>
</head>
<body>
<main>
  <h1>Privacy Notice</h1>
  <p class="muted">Learning 360° Foundation · 'Orange Grove' Block C, Triq L-Ghabex, Swatar BKR 4280, Malta · VO/1863</p>
  <p class="draft"><strong>Draft</strong> — this notice is pending review by the Foundation's legal adviser. Questions in the meantime: info@learning360.org.mt.</p>

  <h2>Who we are</h2>
  <p>Learning 360° Foundation ("the Foundation", "we") provides educational support, coaching and tuition services in Swatar, Malta. We are the data controller for the personal information described below. Contact: info@learning360.org.mt, +356 7942 2001.</p>

  <h2>What we collect and why</h2>
  <ul>
    <li><strong>Parent/guardian details</strong> (names, ID numbers, contact details, address) — to register your family, communicate with you, and invoice for services. Legal basis: performing our agreement with you.</li>
    <li><strong>Learner details</strong> (name, date of birth, school) — to plan and deliver appropriate sessions. Legal basis: performing our agreement with you.</li>
    <li><strong>Health and needs information</strong> (allergies, medical notes, learning needs you choose to share) — to keep learners safe and adapt sessions. Legal basis: your explicit consent, and safeguarding the learner's vital interests. Please share only what we reasonably need.</li>
    <li><strong>Educator information</strong> (identity, right to work, qualifications, safeguarding declarations, referees, bank details) — to vet, engage and pay educators, and to meet child-protection obligations. Legal bases: contract, legal obligation, and our legitimate interest in safeguarding.</li>
    <li><strong>Booking, attendance and payment records</strong> — to run sessions, invoice accurately, and keep the accounting records the law requires. Legal bases: contract and legal obligation.</li>
    <li><strong>Marketing preferences</strong> — we only send news about new services if you opt in, and you can withdraw at any time. Legal basis: consent.</li>
  </ul>

  <h2>Who sees it</h2>
  <p>Information is shared on a need-to-know basis with the Foundation's staff and the tutor working with your learner. We use trusted service providers to run our systems: our booking platform is hosted with Fly.io (Frankfurt, EU) with its database at Neon (EU), and email is provided by Google Workspace. We do not sell personal information or share it with third parties for their own purposes. We may disclose information where the law or a safeguarding duty requires it.</p>

  <h2>How long we keep it</h2>
  <p>For as long as your family or working relationship with the Foundation is active, and afterwards only as long as the law requires (for example accounting records) or as needed to meet safeguarding responsibilities. Specific retention periods are being finalised with our legal adviser <span class="muted">[TBC]</span>.</p>

  <h2>Your rights</h2>
  <p>You can ask us for a copy of your information, ask us to correct or delete it, object to or restrict how we use it, and withdraw any consent you have given. Write to info@learning360.org.mt. You also have the right to complain to Malta's Information and Data Protection Commissioner (idpc.org.mt).</p>

  <p class="muted">Version: draft of 01/09/2026.</p>
</main>
</body>
</html>"""
