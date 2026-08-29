import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Button, Input, Select, Textarea, Wordmark } from "../ui/ui";
import {
  ApiError,
  getEducatorOnboarding,
  submitEducatorOnboarding,
  type EducatorOnboardingSubmitInput,
  type ExperienceRow,
  type QualificationRow,
  type RefereeInput,
} from "../api/client";

// Public educator-onboarding questionnaire (/?educator-onboarding=<token>) —
// the in-app version of the paper "Educator Onboarding Form" v1.0, emailed
// automatically when an educator account is created. Token = auth, no
// sign-in, same pattern as the client onboarding form. Section 15 of the
// paper form (internal checklist) is deliberately NOT here — that's
// admin-side work, not the applicant's.

export const CREDENTIAL_OPTIONS = [
  ["teaching_warrant", "Teaching warrant"],
  ["education_degree", "Education degree"],
  ["tefl_tesol", "TEFL / TESOL"],
  ["sen_training", "SEN / inclusion training"],
  ["first_aid", "First aid"],
  ["paediatric_first_aid", "Paediatric first aid"],
  ["safeguarding_training", "Safeguarding training"],
  ["other_specialist", "Other specialist certification"],
] as const;

export const EXPERIENCE_OPTIONS = [
  ["early_years", "Early years"],
  ["primary", "Primary"],
  ["middle_school", "Middle school"],
  ["secondary", "Secondary"],
  ["post_secondary", "Post-secondary"],
  ["adult_learners", "Adult learners"],
  ["one_to_one", "One-to-one tuition"],
  ["small_groups", "Small groups"],
  ["online_teaching", "Online teaching"],
  ["exam_prep", "Exam preparation"],
  ["learning_difficulties", "Learning difficulties"],
  ["behaviour_support", "Behaviour support"],
] as const;

export const DIGITAL_OPTIONS = [
  ["ms365", "Microsoft 365"],
  ["google_workspace", "Google Workspace"],
  ["zoom_teams", "Zoom / Teams"],
  ["learning_platforms", "Learning platforms"],
  ["interactive_whiteboard", "Interactive whiteboard"],
  ["online_assessment", "Online assessment tools"],
] as const;

export const SESSION_OPTIONS = [
  ["one_to_one", "One-to-one"],
  ["pairs", "Pairs"],
  ["small_groups", "Small groups"],
  ["class_groups", "Class groups"],
  ["online_sessions", "Online sessions"],
  ["home_visits", "Home visits (if approved)"],
  ["school_based", "School-based sessions"],
  ["foundation_premises", "Foundation premises"],
] as const;

export const SG_DOCUMENT_OPTIONS = [
  ["police_conduct", "Recent Police Conduct Certificate"],
  ["minors_clearance", "Protection of Minors / applicable clearance"],
  ["photo_id", "Copy of photo ID"],
  ["safeguarding_cert", "Safeguarding training certificate"],
  ["other_clearance", "Other role-specific clearance"],
] as const;

export const POLICY_OPTIONS = [
  ["safeguarding", "Safeguarding and child-protection policy"],
  ["code_of_conduct", "Code of conduct and professional boundaries"],
  ["data_protection", "Data protection, confidentiality and records management"],
  ["equality", "Equality, diversity, inclusion and anti-harassment"],
  ["health_safety", "Health and safety, emergency and incident reporting"],
  ["attendance", "Attendance, punctuality, cancellation and substitution"],
  ["session_notes", "Session notes, progress reporting and parent/guardian communication"],
  ["premises_it", "Use of premises, equipment, IT and approved communication channels"],
  ["social_media", "Social media, photography and image-consent requirements"],
  ["fees_invoicing", "Fees, invoicing, timesheets and payment procedures"],
  ["complaints", "Complaints, whistleblowing and escalation procedures"],
  ["ip_materials", "Intellectual property and use of teaching materials"],
] as const;

const BOUNDARY_ITEMS: { key: BoundaryKey; label: string }[] = [
  { key: "b_follow_procedures", label: "I will follow Learning 360° safeguarding and child-protection procedures." },
  { key: "b_report_concerns", label: "I will report concerns promptly through the designated safeguarding route." },
  { key: "b_approved_channels", label: "I will use only approved channels to communicate with learners and parents/guardians." },
  { key: "b_no_sharing", label: "I will not share learner information, images or records outside authorised systems." },
  { key: "b_boundaries", label: "I will maintain appropriate physical, digital and professional boundaries." },
];

type BoundaryKey = "b_follow_procedures" | "b_report_concerns" | "b_approved_channels" | "b_no_sharing" | "b_boundaries";

const SG_QUESTIONS: { key: SgKey; text: string }[] = [
  { key: "sg_convicted", text: "Have you ever been convicted, cautioned or formally investigated for an offence relevant to work with children or vulnerable persons?" },
  { key: "sg_proceedings", text: "Are you currently subject to any criminal proceedings, safeguarding inquiry, restriction, barring decision or disciplinary process?" },
  { key: "sg_dismissed", text: "Have you ever been dismissed, suspended, sanctioned or asked to leave a role because of safeguarding, professional conduct or boundary concerns?" },
  { key: "sg_other_matters", text: "Is there any other matter that may reasonably affect your suitability for this work?" },
];

type SgKey = "sg_convicted" | "sg_proceedings" | "sg_dismissed" | "sg_other_matters";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const emptyQualification = (): QualificationRow => ({ qualification: "", institution: "", year: "", level_result: "" });
const emptyExperience = (): ExperienceRow => ({ organisation: "", role_subjects: "", learner_ages: "", from_when: "", to_when: "" });
const emptyReferee = (): RefereeInput => ({
  name_position: "", organisation: "", relationship: "", email: "", phone: "", known_since: "", contact_now: null, contact_after: "",
});

function initialForm(): EducatorOnboardingSubmitInput {
  return {
    role_applied_for: "", subjects_services: "", preferred_start_date: "", engagement_type: "tbc",
    referred_by: "", existing_contact: "",
    full_legal_name: "", preferred_name: "", former_names: "", date_of_birth: "", id_passport_number: "",
    nationality: "", residential_address: "", postcode_country: "", mobile: "", email: "",
    preferred_contact: "email", right_to_work: "yes", permit_basis: "", permit_basis_other: "",
    permit_number: "", permit_expiry: "",
    emergency_name: "", emergency_relationship: "", emergency_phone: "", emergency_alt_phone: "",
    medical_conditions: "", medication_action: "", accessibility_needs: "",
    qualifications: [emptyQualification()], credentials: [], warrant_number: "", issuing_body: "",
    warrant_expiry: "", languages_spoken: "", languages_taught: "",
    experience: [emptyExperience()], experience_areas: [], teaching_profile: "",
    subjects_levels_boards: "", inclusive_approach: "",
    digital_skills: [], own_device: null, reliable_internet: null, other_software: "",
    availability: DAYS.map((day) => ({ day, available_from: "", available_until: "", on_site: false, online: false, notes: "" })),
    min_hours_weekly: "", max_hours_weekly: "", holidays_available: "", notice_needed: "",
    unavailable_dates: "", preferred_ages: "", preferred_locations: "", willing_travel: "",
    travel_within: "", own_transport: "",
    session_preferences: [], session_restrictions: "",
    sg_convicted: "no", sg_proceedings: "no", sg_dismissed: "no", sg_other_matters: "no",
    sg_documents: [], clearance_date: "", clearance_reference: "", clearance_renewal: "",
    b_follow_procedures: false, b_report_concerns: false, b_approved_channels: false,
    b_no_sharing: false, b_boundaries: false,
    referee1: emptyReferee(), referee2: emptyReferee(), referee_authorisation: false,
    payment_basis: "", payment_basis_other: "", tax_vat_number: "", social_security_number: "",
    business_name: "", invoice_email: "", bank_account_holder: "", iban: "", bic: "",
    policies_ack: [],
    dp_accuracy: false, dp_processing: false, dp_marketing: false, dp_queries: "",
    signature_name: "", signed_date: new Date().toISOString().slice(0, 10),
  };
}

function Section({ number, title, hint, children }: { number: number; title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="l360-ob-section">
      <h2 className="l360-ob-section-title">{number}. {title}</h2>
      {hint && <p className="l360-ob-section-hint">{hint}</p>}
      {children}
    </section>
  );
}

function CheckGroup({
  idPrefix, options, selected, onChange, legend,
}: {
  idPrefix: string;
  options: readonly (readonly [string, string])[];
  selected: string[];
  onChange: (next: string[]) => void;
  legend?: string;
}) {
  function toggle(value: string, on: boolean) {
    onChange(on ? [...selected, value] : selected.filter((v) => v !== value));
  }
  return (
    <fieldset className="l360-ob-radio-group">
      {legend && <legend className="l360-field-label">{legend}</legend>}
      {options.map(([value, label]) => (
        <div className="l360-ob-check" key={value}>
          <input
            id={`${idPrefix}-${value}`}
            type="checkbox"
            checked={selected.includes(value)}
            onChange={(e) => toggle(value, e.target.checked)}
          />
          <label htmlFor={`${idPrefix}-${value}`}>{label}</label>
        </div>
      ))}
    </fieldset>
  );
}

function ChoiceRow({
  legend, name, options, value, onChange,
}: {
  legend: string;
  name: string;
  options: readonly (readonly [string, string])[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <fieldset className="l360-ob-radio-group">
      <legend className="l360-field-label">{legend}</legend>
      <div className="l360-ob-radio-row" style={{ flexWrap: "wrap" }}>
        {options.map(([v, label]) => (
          <label key={v}>
            <input type="radio" name={name} checked={value === v} onChange={() => onChange(v)} /> {label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

type PageState = "loading" | "invalid" | "form" | "done";

export function EducatorOnboarding({ token }: { token: string }) {
  const [pageState, setPageState] = useState<PageState>("loading");
  const [alreadySubmitted, setAlreadySubmitted] = useState(false);
  const [f, setF] = useState<EducatorOnboardingSubmitInput>(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function set<K extends keyof EducatorOnboardingSubmitInput>(key: K, value: EducatorOnboardingSubmitInput[K]) {
    setF((prev) => ({ ...prev, [key]: value }));
  }

  function setReferee(which: "referee1" | "referee2", key: keyof RefereeInput, value: string | boolean | null) {
    setF((prev) => ({ ...prev, [which]: { ...prev[which], [key]: value } }));
  }

  function setRow<T>(listKey: "qualifications" | "experience" | "availability", index: number, key: string, value: T) {
    setF((prev) => {
      const list = [...(prev[listKey] as unknown[])] as Record<string, unknown>[];
      list[index] = { ...list[index], [key]: value };
      return { ...prev, [listKey]: list };
    });
  }

  useEffect(() => {
    getEducatorOnboarding(token)
      .then((p) => {
        if (p.status === "submitted") {
          setAlreadySubmitted(true);
          setPageState("done");
          return;
        }
        setF((prev) => ({ ...prev, full_legal_name: p.full_name, email: p.email }));
        setPageState("form");
      })
      .catch(() => setPageState("invalid"));
  }, [token]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!f.full_legal_name.trim() || !f.date_of_birth || !f.id_passport_number.trim() || !f.residential_address.trim() || !f.mobile.trim() || !f.email.trim()) {
      setError("Please complete your personal details — full legal name, date of birth, ID/passport number, address, mobile and email are all required.");
      return;
    }
    if (!f.emergency_name.trim() || !f.emergency_phone.trim()) {
      setError("Please give us an emergency contact name and phone number.");
      return;
    }
    if (!f.b_follow_procedures || !f.b_report_concerns || !f.b_approved_channels || !f.b_no_sharing || !f.b_boundaries) {
      setError("Please tick each of the five professional-boundaries acknowledgements — they're required to work with our learners.");
      return;
    }
    if (!f.referee_authorisation) {
      setError("Please authorise us to contact your referees.");
      return;
    }
    if (!f.dp_accuracy || !f.dp_processing) {
      setError("Please confirm the two required data-protection statements.");
      return;
    }
    if (!f.signature_name.trim() || !f.signed_date) {
      setError("Please sign (type your full name) and date the declaration.");
      return;
    }
    setSubmitting(true);
    try {
      const clean: EducatorOnboardingSubmitInput = {
        ...f,
        qualifications: f.qualifications.filter((q) => Object.values(q).some((v) => String(v).trim())),
        experience: f.experience.filter((q) => Object.values(q).some((v) => String(v).trim())),
      };
      await submitEducatorOnboarding(token, clean);
      setAlreadySubmitted(false);
      setPageState("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (pageState === "loading") {
    return (
      <div className="l360-ob-page">
        <p style={{ color: "var(--l360-white)" }}>Loading…</p>
      </div>
    );
  }

  if (pageState === "invalid") {
    return (
      <div className="l360-ob-page">
        <div className="l360-ob-card">
          <Wordmark className="l360-login-wordmark" />
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ This onboarding link isn't valid any more. Please contact Learning 360° Foundation for a fresh link.
          </div>
        </div>
      </div>
    );
  }

  if (pageState === "done") {
    return (
      <div className="l360-ob-page">
        <div className="l360-ob-card">
          <Wordmark className="l360-login-wordmark" />
          <h1 className="l360-ob-title">{alreadySubmitted ? "Already completed" : "Thank you!"}</h1>
          <p className="l360-ob-intro">
            {alreadySubmitted
              ? "This onboarding form has already been submitted — there's nothing more to do. If any of your details change, just let us know."
              : "We've received your onboarding form and emailed you a confirmation. We'll review it, complete the remaining checks, and be in touch about next steps."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="l360-ob-page">
      <form className="l360-ob-card" onSubmit={handleSubmit} noValidate>
        <Wordmark className="l360-login-wordmark" />
        <h1 className="l360-ob-title">Educator onboarding form</h1>
        <p className="l360-ob-intro">
          Please complete all applicable sections; leave anything that doesn't apply blank.
          Information supplied is handled confidentially and used for recruitment, onboarding,
          safeguarding, scheduling, payment and legal compliance.
        </p>

        <Section number={1} title="Application overview">
          <div className="l360-ob-grid">
            <Input id="eo-role" label="Role applied for" value={f.role_applied_for} onChange={(e) => set("role_applied_for", e.target.value)} />
            <Input id="eo-subjects" label="Subject(s) / service(s)" value={f.subjects_services} onChange={(e) => set("subjects_services", e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-start" label="Preferred start date" type="date" value={f.preferred_start_date} onChange={(e) => set("preferred_start_date", e.target.value)} />
            <Select
              id="eo-engagement"
              label="Engagement type"
              options={[
                { value: "employee", label: "Employee" },
                { value: "self_employed", label: "Self-employed" },
                { value: "sessional", label: "Sessional contractor" },
                { value: "tbc", label: "To be confirmed" },
              ]}
              value={f.engagement_type}
              onChange={(e) => set("engagement_type", e.target.value as EducatorOnboardingSubmitInput["engagement_type"])}
            />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-referred" label="Referred by" value={f.referred_by} onChange={(e) => set("referred_by", e.target.value)} />
            <Input id="eo-contact" label="Existing Learning 360° contact" value={f.existing_contact} onChange={(e) => set("existing_contact", e.target.value)} />
          </div>
        </Section>

        <Section number={2} title="Personal and contact details">
          <div className="l360-ob-grid">
            <Input id="eo-legal-name" label="Full legal name" required value={f.full_legal_name} onChange={(e) => set("full_legal_name", e.target.value)} autoComplete="name" />
            <Input id="eo-pref-name" label="Preferred name" value={f.preferred_name} onChange={(e) => set("preferred_name", e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-former" label="Former name(s), if relevant" value={f.former_names} onChange={(e) => set("former_names", e.target.value)} />
            <Input id="eo-dob" label="Date of birth" type="date" required value={f.date_of_birth} onChange={(e) => set("date_of_birth", e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-id" label="ID / passport number" required value={f.id_passport_number} onChange={(e) => set("id_passport_number", e.target.value)} />
            <Input id="eo-nationality" label="Nationality" value={f.nationality} onChange={(e) => set("nationality", e.target.value)} />
          </div>
          <Textarea id="eo-address" label="Residential address" required rows={2} value={f.residential_address} onChange={(e) => set("residential_address", e.target.value)} autoComplete="street-address" />
          <div className="l360-ob-grid">
            <Input id="eo-postcode" label="Postcode / country" value={f.postcode_country} onChange={(e) => set("postcode_country", e.target.value)} />
            <Input id="eo-mobile" label="Mobile number" type="tel" required value={f.mobile} onChange={(e) => set("mobile", e.target.value)} autoComplete="tel" />
          </div>
          <Input id="eo-email" label="Email address" type="email" required value={f.email} onChange={(e) => set("email", e.target.value)} autoComplete="email" />
          <ChoiceRow
            legend="Preferred contact"
            name="eo-pref-contact"
            options={[["phone", "Phone"], ["email", "Email"], ["whatsapp", "WhatsApp"]]}
            value={f.preferred_contact}
            onChange={(v) => set("preferred_contact", v as EducatorOnboardingSubmitInput["preferred_contact"])}
          />
          <ChoiceRow
            legend="Authorised to work in Malta?"
            name="eo-rtw"
            options={[["yes", "Yes"], ["no", "No"], ["pending", "Pending"]]}
            value={f.right_to_work}
            onChange={(v) => set("right_to_work", v as EducatorOnboardingSubmitInput["right_to_work"])}
          />
          <ChoiceRow
            legend="Basis / permit type"
            name="eo-permit-basis"
            options={[["maltese_eu", "Maltese / EU / EEA / Swiss"], ["single_permit", "Single Permit"], ["other", "Other"]]}
            value={f.permit_basis}
            onChange={(v) => set("permit_basis", v as EducatorOnboardingSubmitInput["permit_basis"])}
          />
          {f.permit_basis === "other" && (
            <Input id="eo-permit-other" label="Other basis" value={f.permit_basis_other} onChange={(e) => set("permit_basis_other", e.target.value)} />
          )}
          {f.permit_basis === "single_permit" && (
            <div className="l360-ob-grid">
              <Input id="eo-permit-no" label="Permit number" value={f.permit_number} onChange={(e) => set("permit_number", e.target.value)} />
              <Input id="eo-permit-exp" label="Permit expiry date" type="date" value={f.permit_expiry} onChange={(e) => set("permit_expiry", e.target.value)} />
            </div>
          )}
        </Section>

        <Section
          number={3}
          title="Emergency contact and health information"
          hint="Only disclose health, allergy, access or support information that Learning 360° reasonably needs to protect you or others and to make appropriate workplace arrangements."
        >
          <div className="l360-ob-grid">
            <Input id="eo-em-name" label="Emergency contact name" required value={f.emergency_name} onChange={(e) => set("emergency_name", e.target.value)} />
            <Input id="eo-em-rel" label="Relationship" value={f.emergency_relationship} onChange={(e) => set("emergency_relationship", e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-em-phone" label="Primary phone" type="tel" required value={f.emergency_phone} onChange={(e) => set("emergency_phone", e.target.value)} />
            <Input id="eo-em-alt" label="Alternative phone" type="tel" value={f.emergency_alt_phone} onChange={(e) => set("emergency_alt_phone", e.target.value)} />
          </div>
          <Textarea id="eo-medical" label="Relevant medical condition / allergy" rows={2} value={f.medical_conditions} onChange={(e) => set("medical_conditions", e.target.value)} />
          <Textarea id="eo-medication" label="Medication or emergency action" rows={2} value={f.medication_action} onChange={(e) => set("medication_action", e.target.value)} />
          <Textarea id="eo-access" label="Accessibility / reasonable adjustment" rows={2} value={f.accessibility_needs} onChange={(e) => set("accessibility_needs", e.target.value)} />
        </Section>

        <Section number={4} title="Education, qualifications and professional registration">
          {f.qualifications.map((q, i) => (
            <div className="l360-ob-grid" key={i}>
              <Input id={`eo-q-${i}-name`} label={`Qualification / award ${i + 1}`} value={q.qualification} onChange={(e) => setRow("qualifications", i, "qualification", e.target.value)} />
              <Input id={`eo-q-${i}-inst`} label="Institution" value={q.institution} onChange={(e) => setRow("qualifications", i, "institution", e.target.value)} />
              <Input id={`eo-q-${i}-year`} label="Year" value={q.year} onChange={(e) => setRow("qualifications", i, "year", e.target.value)} />
              <Input id={`eo-q-${i}-level`} label="Level / result" value={q.level_result} onChange={(e) => setRow("qualifications", i, "level_result", e.target.value)} />
            </div>
          ))}
          {f.qualifications.length < 10 && (
            <Button type="button" variant="secondary" onClick={() => set("qualifications", [...f.qualifications, emptyQualification()])}>
              Add another qualification
            </Button>
          )}
          <CheckGroup idPrefix="eo-cred" legend="Teaching and specialist credentials" options={CREDENTIAL_OPTIONS} selected={f.credentials} onChange={(v) => set("credentials", v)} />
          <div className="l360-ob-grid">
            <Input id="eo-warrant" label="Warrant / registration number" value={f.warrant_number} onChange={(e) => set("warrant_number", e.target.value)} />
            <Input id="eo-issuing" label="Issuing body" value={f.issuing_body} onChange={(e) => set("issuing_body", e.target.value)} />
            <Input id="eo-warrant-exp" label="Expiry / renewal date" value={f.warrant_expiry} onChange={(e) => set("warrant_expiry", e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-lang-spoken" label="Languages spoken" value={f.languages_spoken} onChange={(e) => set("languages_spoken", e.target.value)} />
            <Input id="eo-lang-taught" label="Languages taught in" value={f.languages_taught} onChange={(e) => set("languages_taught", e.target.value)} />
          </div>
        </Section>

        <Section number={5} title="Employment and teaching experience">
          {f.experience.map((x, i) => (
            <div className="l360-ob-grid" key={i}>
              <Input id={`eo-x-${i}-org`} label={`Organisation ${i + 1}`} value={x.organisation} onChange={(e) => setRow("experience", i, "organisation", e.target.value)} />
              <Input id={`eo-x-${i}-role`} label="Role / subjects" value={x.role_subjects} onChange={(e) => setRow("experience", i, "role_subjects", e.target.value)} />
              <Input id={`eo-x-${i}-ages`} label="Learner ages" value={x.learner_ages} onChange={(e) => setRow("experience", i, "learner_ages", e.target.value)} />
              <Input id={`eo-x-${i}-from`} label="From" value={x.from_when} onChange={(e) => setRow("experience", i, "from_when", e.target.value)} />
              <Input id={`eo-x-${i}-to`} label="To" value={x.to_when} onChange={(e) => setRow("experience", i, "to_when", e.target.value)} />
            </div>
          ))}
          {f.experience.length < 10 && (
            <Button type="button" variant="secondary" onClick={() => set("experience", [...f.experience, emptyExperience()])}>
              Add another role
            </Button>
          )}
          <CheckGroup idPrefix="eo-exp" legend="Relevant experience" options={EXPERIENCE_OPTIONS} selected={f.experience_areas} onChange={(v) => set("experience_areas", v)} />
          <Textarea id="eo-profile" label="Brief teaching profile" rows={4} value={f.teaching_profile} onChange={(e) => set("teaching_profile", e.target.value)} />
          <Textarea id="eo-boards" label="Subjects, levels and exam boards" rows={2} value={f.subjects_levels_boards} onChange={(e) => set("subjects_levels_boards", e.target.value)} />
          <Textarea id="eo-inclusive" label="Approach to inclusive learning" rows={4} value={f.inclusive_approach} onChange={(e) => set("inclusive_approach", e.target.value)} />
        </Section>

        <Section number={6} title="Digital skills and resources">
          <CheckGroup idPrefix="eo-dig" options={DIGITAL_OPTIONS} selected={f.digital_skills} onChange={(v) => set("digital_skills", v)} />
          <ChoiceRow legend="Own suitable laptop/device?" name="eo-device" options={[["yes", "Yes"], ["no", "No"]]} value={f.own_device === true ? "yes" : f.own_device === false ? "no" : ""} onChange={(v) => set("own_device", v === "yes")} />
          <ChoiceRow legend="Reliable internet for online sessions?" name="eo-internet" options={[["yes", "Yes"], ["no", "No"]]} value={f.reliable_internet === true ? "yes" : f.reliable_internet === false ? "no" : ""} onChange={(v) => set("reliable_internet", v === "yes")} />
          <Input id="eo-software" label="Other useful software / skills" value={f.other_software} onChange={(e) => set("other_software", e.target.value)} />
        </Section>

        <Section
          number={7}
          title="Availability and scheduling"
          hint="Enter the earliest and latest times you are normally available. Final hours remain subject to learner demand and written confirmation."
        >
          {f.availability.map((a, i) => (
            <div className="l360-ob-grid" key={a.day} style={{ alignItems: "flex-end" }}>
              <div className="l360-field" style={{ flex: "0 0 110px" }}>
                <span className="l360-field-label">{a.day}</span>
              </div>
              <Input id={`eo-av-${i}-from`} label="From" type="time" value={a.available_from} onChange={(e) => setRow("availability", i, "available_from", e.target.value)} />
              <Input id={`eo-av-${i}-until`} label="Until" type="time" value={a.available_until} onChange={(e) => setRow("availability", i, "available_until", e.target.value)} />
              <div className="l360-ob-check" style={{ marginTop: 0 }}>
                <input id={`eo-av-${i}-onsite`} type="checkbox" checked={a.on_site} onChange={(e) => setRow("availability", i, "on_site", e.target.checked)} />
                <label htmlFor={`eo-av-${i}-onsite`}>On-site</label>
              </div>
              <div className="l360-ob-check" style={{ marginTop: 0 }}>
                <input id={`eo-av-${i}-online`} type="checkbox" checked={a.online} onChange={(e) => setRow("availability", i, "online", e.target.checked)} />
                <label htmlFor={`eo-av-${i}-online`}>Online</label>
              </div>
            </div>
          ))}
          <div className="l360-ob-grid">
            <Input id="eo-min-hours" label="Minimum hours sought weekly" value={f.min_hours_weekly} onChange={(e) => set("min_hours_weekly", e.target.value)} />
            <Input id="eo-max-hours" label="Maximum hours available weekly" value={f.max_hours_weekly} onChange={(e) => set("max_hours_weekly", e.target.value)} />
          </div>
          <ChoiceRow legend="Available during school holidays?" name="eo-holidays" options={[["yes", "Yes"], ["no", "No"], ["some", "Some periods"]]} value={f.holidays_available} onChange={(v) => set("holidays_available", v as EducatorOnboardingSubmitInput["holidays_available"])} />
          <div className="l360-ob-grid">
            <Input id="eo-notice" label="Notice needed for timetable changes" value={f.notice_needed} onChange={(e) => set("notice_needed", e.target.value)} />
            <Input id="eo-unavailable" label="Known unavailable dates" value={f.unavailable_dates} onChange={(e) => set("unavailable_dates", e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-pref-ages" label="Preferred learner age groups" value={f.preferred_ages} onChange={(e) => set("preferred_ages", e.target.value)} />
            <Input id="eo-pref-loc" label="Preferred locations" value={f.preferred_locations} onChange={(e) => set("preferred_locations", e.target.value)} />
          </div>
          <ChoiceRow legend="Willing to travel between locations?" name="eo-travel" options={[["yes", "Yes"], ["no", "No"], ["within", "Within a distance"]]} value={f.willing_travel} onChange={(v) => set("willing_travel", v as EducatorOnboardingSubmitInput["willing_travel"])} />
          {f.willing_travel === "within" && (
            <Input id="eo-travel-within" label="Within" value={f.travel_within} onChange={(e) => set("travel_within", e.target.value)} />
          )}
          <ChoiceRow legend="Own transport / valid licence?" name="eo-transport" options={[["yes", "Yes"], ["no", "No"], ["na", "Not applicable"]]} value={f.own_transport} onChange={(v) => set("own_transport", v as EducatorOnboardingSubmitInput["own_transport"])} />
        </Section>

        <Section number={8} title="Session preferences">
          <CheckGroup idPrefix="eo-sess" options={SESSION_OPTIONS} selected={f.session_preferences} onChange={(v) => set("session_preferences", v)} />
          <Textarea id="eo-sess-notes" label="Restrictions or preferences" rows={2} value={f.session_restrictions} onChange={(e) => set("session_restrictions", e.target.value)} />
        </Section>

        <Section
          number={9}
          title="Safeguarding and suitability declaration"
          hint="Learning 360° works with children and potentially vulnerable persons. Answer every question truthfully. A 'Yes' response will be assessed fairly and does not automatically prevent engagement, but withholding relevant information may do so."
        >
          {SG_QUESTIONS.map((q) => (
            <ChoiceRow
              key={q.key}
              legend={q.text}
              name={`eo-${q.key}`}
              options={[["no", "No"], ["yes", "Yes — provide details separately"]]}
              value={f[q.key]}
              onChange={(v) => set(q.key, v as "no" | "yes")}
            />
          ))}
          <CheckGroup idPrefix="eo-sgdoc" legend="Safeguarding documents you can provide" options={SG_DOCUMENT_OPTIONS} selected={f.sg_documents} onChange={(v) => set("sg_documents", v)} />
          <div className="l360-ob-grid">
            <Input id="eo-clear-date" label="Certificate / clearance date" value={f.clearance_date} onChange={(e) => set("clearance_date", e.target.value)} />
            <Input id="eo-clear-ref" label="Reference number" value={f.clearance_reference} onChange={(e) => set("clearance_reference", e.target.value)} />
            <Input id="eo-clear-renewal" label="Renewal required by" value={f.clearance_renewal} onChange={(e) => set("clearance_renewal", e.target.value)} />
          </div>
          <p className="l360-ob-policy"><strong>Professional boundaries acknowledgement</strong></p>
          {BOUNDARY_ITEMS.map((b) => (
            <div className="l360-ob-check" key={b.key}>
              <input id={`eo-${b.key}`} type="checkbox" checked={f[b.key]} onChange={(e) => set(b.key, e.target.checked)} />
              <label htmlFor={`eo-${b.key}`}>{b.label}</label>
            </div>
          ))}
        </Section>

        <Section
          number={10}
          title="References"
          hint="Please provide two referees, preferably including your current or most recent employer and someone able to comment on your suitability to work with learners. Referees should not be relatives."
        >
          {(["referee1", "referee2"] as const).map((which, idx) => (
            <div key={which}>
              <p className="l360-ob-policy"><strong>Referee {idx + 1}</strong></p>
              <div className="l360-ob-grid">
                <Input id={`eo-${which}-name`} label="Name and position" value={f[which].name_position} onChange={(e) => setReferee(which, "name_position", e.target.value)} />
                <Input id={`eo-${which}-org`} label="Organisation" value={f[which].organisation} onChange={(e) => setReferee(which, "organisation", e.target.value)} />
              </div>
              <div className="l360-ob-grid">
                <Input id={`eo-${which}-rel`} label="Relationship to you" value={f[which].relationship} onChange={(e) => setReferee(which, "relationship", e.target.value)} />
                <Input id={`eo-${which}-since`} label="Known since" value={f[which].known_since} onChange={(e) => setReferee(which, "known_since", e.target.value)} />
              </div>
              <div className="l360-ob-grid">
                <Input id={`eo-${which}-email`} label="Email" type="email" value={f[which].email} onChange={(e) => setReferee(which, "email", e.target.value)} />
                <Input id={`eo-${which}-phone`} label="Phone" type="tel" value={f[which].phone} onChange={(e) => setReferee(which, "phone", e.target.value)} />
              </div>
              <ChoiceRow
                legend="May we contact now?"
                name={`eo-${which}-now`}
                options={[["yes", "Yes"], ["no", "No — contact after a date"]]}
                value={f[which].contact_now === true ? "yes" : f[which].contact_now === false ? "no" : ""}
                onChange={(v) => setReferee(which, "contact_now", v === "yes")}
              />
              {f[which].contact_now === false && (
                <Input id={`eo-${which}-after`} label="Contact after" value={f[which].contact_after} onChange={(e) => setReferee(which, "contact_after", e.target.value)} />
              )}
            </div>
          ))}
          <div className="l360-ob-check">
            <input id="eo-ref-auth" type="checkbox" checked={f.referee_authorisation} onChange={(e) => set("referee_authorisation", e.target.checked)} />
            <label htmlFor="eo-ref-auth">I authorise Learning 360° to contact the referees above and verify information relevant to my application.</label>
          </div>
        </Section>

        <Section
          number={11}
          title="Payment and tax information"
          hint="Rates, employment status and payment terms are valid only when confirmed in the applicable written agreement. Bank details are verified through Learning 360°'s approved process before the first payment."
        >
          <ChoiceRow legend="Payment basis" name="eo-pay-basis" options={[["payroll", "Payroll"], ["self_invoice", "Self-employed invoice"], ["other", "Other"]]} value={f.payment_basis} onChange={(v) => set("payment_basis", v as EducatorOnboardingSubmitInput["payment_basis"])} />
          {f.payment_basis === "other" && (
            <Input id="eo-pay-other" label="Other payment basis" value={f.payment_basis_other} onChange={(e) => set("payment_basis_other", e.target.value)} />
          )}
          <div className="l360-ob-grid">
            <Input id="eo-tax" label="Tax / VAT number, if applicable" value={f.tax_vat_number} onChange={(e) => set("tax_vat_number", e.target.value)} />
            <Input id="eo-ssn" label="Social security number" value={f.social_security_number} onChange={(e) => set("social_security_number", e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-business" label="Registered business name" value={f.business_name} onChange={(e) => set("business_name", e.target.value)} />
            <Input id="eo-inv-email" label="Invoice email" type="email" value={f.invoice_email} onChange={(e) => set("invoice_email", e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="eo-holder" label="Bank account holder" value={f.bank_account_holder} onChange={(e) => set("bank_account_holder", e.target.value)} />
            <Input id="eo-iban" label="IBAN" value={f.iban} onChange={(e) => set("iban", e.target.value)} />
            <Input id="eo-bic" label="BIC / SWIFT" value={f.bic} onChange={(e) => set("bic", e.target.value)} />
          </div>
        </Section>

        <Section number={12} title="Policies and onboarding acknowledgements" hint="Tick each policy as you receive and read it — anything left unticked will be covered during induction.">
          <CheckGroup idPrefix="eo-pol" options={POLICY_OPTIONS} selected={f.policies_ack} onChange={(v) => set("policies_ack", v)} />
        </Section>

        <Section
          number={13}
          title="Data protection notice and consent choices"
          hint="Learning 360° Foundation will process the information in this form to assess suitability, complete onboarding, manage the working relationship, safeguard learners, arrange sessions, administer payment and meet legal obligations. Relevant information may be shared on a need-to-know basis with authorised staff, professional advisers, regulators, safeguarding bodies, referees, payroll providers and clients/parents where lawful and necessary."
        >
          <div className="l360-ob-check">
            <input id="eo-dp-accuracy" type="checkbox" checked={f.dp_accuracy} onChange={(e) => set("dp_accuracy", e.target.checked)} />
            <label htmlFor="eo-dp-accuracy">I confirm that the information supplied is accurate and may be verified for onboarding and compliance purposes.</label>
          </div>
          <div className="l360-ob-check">
            <input id="eo-dp-processing" type="checkbox" checked={f.dp_processing} onChange={(e) => set("dp_processing", e.target.checked)} />
            <label htmlFor="eo-dp-processing">I understand that essential processing for recruitment, contract administration, safeguarding and legal compliance does not depend solely on consent.</label>
          </div>
          <div className="l360-ob-check">
            <input id="eo-dp-marketing" type="checkbox" checked={f.dp_marketing} onChange={(e) => set("dp_marketing", e.target.checked)} />
            <label htmlFor="eo-dp-marketing">Optional: I consent to receiving non-essential Learning 360° news and opportunities. I may withdraw this consent at any time.</label>
          </div>
          <Textarea id="eo-dp-queries" label="Data-protection queries / special instructions" rows={2} value={f.dp_queries} onChange={(e) => set("dp_queries", e.target.value)} />
        </Section>

        <Section
          number={14}
          title="Applicant declaration"
          hint="I declare that the information provided is complete and true to the best of my knowledge. I will notify Learning 360° promptly if relevant circumstances, qualifications, permissions, contact details, availability or safeguarding information change. I understand that engagement remains conditional upon satisfactory checks, references, right-to-work verification, applicable clearances, acceptance of policies and execution of the appropriate written agreement."
        >
          <div className="l360-ob-grid">
            <Input id="eo-sig" label="Signature (type your full name)" required value={f.signature_name} onChange={(e) => set("signature_name", e.target.value)} />
            <Input id="eo-sig-date" label="Date" type="date" required value={f.signed_date} onChange={(e) => set("signed_date", e.target.value)} />
          </div>
        </Section>

        {error && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {error}
          </div>
        )}

        <Button type="submit" block loading={submitting} loadingLabel="Submitting…">
          Submit onboarding form
        </Button>
        <p className="l360-ob-footnote">
          Information supplied is handled confidentially by Learning 360° Foundation and used only for
          recruitment, onboarding, safeguarding, scheduling, payment and legal compliance.
        </p>
      </form>
    </div>
  );
}
