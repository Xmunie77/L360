import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Button, Input, Textarea, Wordmark } from "../ui/ui";
import {
  ApiError,
  getOnboarding,
  submitOnboarding,
  type OnboardingPrefill,
} from "../api/client";

// The public client-onboarding questionnaire, reached from the link emailed
// when an admin adds a client (/?onboarding=<token>). No account needed — the
// unguessable token is the auth. Field set and legal copy mirror the original
// Google "Client Onboarding Form" so the record we store is the same record
// guardians have always agreed to.

// Verbatim policy/consent copy (typos in the original tidied, meaning intact).
const COPY = {
  intro:
    "Kindly fill in the below for Learning 360° Foundation's client database. " +
    "Learning 360° Foundation will not share any of the information provided with a third party.",
  fee:
    "I undertake to pay all fees due for the services rendered to the minor under my care " +
    "or for the learner of legal age by Learning 360° Foundation.",
  termination:
    "I understand that Learning 360° Foundation has the right to terminate services " +
    "if payment for services is not received for more than 60 days.",
  infoStorage:
    "I agree to have my information stored by Learning 360° Foundation and shared " +
    "with the relevant tutor if or when necessary.",
  marketing:
    "Would you like to be kept informed about new services offered by Learning 360° Foundation?",
  epinephrine:
    "I understand that if the learner has an allergy, the Educators at Learning 360° Foundation " +
    "are not trained to use Epipens or allergy medication nor will be responsible to do so.",
  accident:
    "I acknowledge that educators at Learning 360° Foundation are not to be held liable for any " +
    "accidents that may occur while a learner is in their care. Parents/guardians are kindly " +
    "requested to remain in the waiting area until the child has completed their session.",
  cancellation:
    "Sessions need to be cancelled at least 24 hours in advance. A cancellation fee may apply; " +
    "however, this will be considered at the discretion of the supervisor in cases of sudden " +
    "illness or unforeseen emergencies.",
  illness:
    "If your child is unwell or showing signs of illness, we kindly ask that you cancel the " +
    "session in advance. As we work closely with a number of vulnerable children, we aim to " +
    "minimise the spread of illness wherever possible.",
};

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="l360-ob-section">
      <h2 className="l360-ob-section-title">{title}</h2>
      {hint && <p className="l360-ob-section-hint">{hint}</p>}
      {children}
    </section>
  );
}

function AgreeCheck({
  id,
  text,
  checked,
  onChange,
}: {
  id: string;
  text: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="l360-ob-check">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <label htmlFor={id}>{text}</label>
    </div>
  );
}

function YesNo({
  legend,
  name,
  value,
  onChange,
}: {
  legend: string;
  name: string;
  value: boolean | null;
  onChange: (v: boolean) => void;
}) {
  return (
    <fieldset className="l360-ob-radio-group">
      <legend className="l360-field-label">{legend} *</legend>
      <div className="l360-ob-radio-row">
        <label>
          <input type="radio" name={name} checked={value === true} onChange={() => onChange(true)} /> Yes
        </label>
        <label>
          <input type="radio" name={name} checked={value === false} onChange={() => onChange(false)} /> No
        </label>
      </div>
    </fieldset>
  );
}

type PageState = "loading" | "invalid" | "form" | "done";

export function Onboarding({ token }: { token: string }) {
  const [pageState, setPageState] = useState<PageState>("loading");
  const [alreadySubmitted, setAlreadySubmitted] = useState(false);

  // Guardian 1
  const [firstName, setFirstName] = useState("");
  const [surname, setSurname] = useState("");
  const [idNumber, setIdNumber] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  // Guardian 2 (optional)
  const [g2Name, setG2Name] = useState("");
  const [g2Id, setG2Id] = useState("");
  const [g2Email, setG2Email] = useState("");
  const [g2Phone, setG2Phone] = useState("");
  // Learner
  const [childName, setChildName] = useState("");
  const [childDob, setChildDob] = useState("");
  const [school, setSchool] = useState("");
  const [address, setAddress] = useState("");
  const [hasAllergies, setHasAllergies] = useState<boolean | null>(null);
  const [allergyDetails, setAllergyDetails] = useState("");
  // Consents
  const [epinephrineAck, setEpinephrineAck] = useState(false);
  const [accidentAck, setAccidentAck] = useState(false);
  const [feeUndertaking, setFeeUndertaking] = useState(false);
  const [terminationAck, setTerminationAck] = useState(false);
  const [infoStorage, setInfoStorage] = useState(false);
  const [marketing, setMarketing] = useState<boolean | null>(null);
  const [cancellationAck, setCancellationAck] = useState(false);
  const [illnessAck, setIllnessAck] = useState(false);
  // Signatures
  const [signature1, setSignature1] = useState("");
  const [signature2, setSignature2] = useState("");
  const [signedDate, setSignedDate] = useState(() => new Date().toISOString().slice(0, 10));

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getOnboarding(token)
      .then((p: OnboardingPrefill) => {
        if (p.status === "submitted") {
          setAlreadySubmitted(true);
          setPageState("done");
          return;
        }
        setFirstName(p.guardian_first_name);
        setSurname(p.guardian_surname);
        setEmail(p.email);
        setPhone(p.phone ?? "");
        setIdNumber(p.guardian_id_number ?? "");
        setG2Name(p.guardian2_name ?? "");
        setG2Id(p.guardian2_id_number ?? "");
        setG2Email(p.guardian2_email ?? "");
        setG2Phone(p.guardian2_phone ?? "");
        setChildName(p.child_name ?? "");
        setChildDob(p.child_dob ?? "");
        setSchool(p.school ?? "");
        setAddress(p.address ?? "");
        setHasAllergies(p.has_allergies);
        setAllergyDetails(p.allergy_details ?? "");
        setPageState("form");
      })
      .catch(() => setPageState("invalid"));
  }, [token]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!firstName.trim() || !surname.trim() || !idNumber.trim() || !email.trim() || !phone.trim()) {
      setError("Please fill in all of Parent/Guardian 1's details.");
      return;
    }
    if (!childName.trim() || !childDob || !address.trim()) {
      setError("Please fill in the learner's name, date of birth and address.");
      return;
    }
    if (hasAllergies === null) {
      setError("Please tell us whether the learner has any allergies.");
      return;
    }
    if (hasAllergies && !allergyDetails.trim()) {
      setError("Please specify the learner's allergies.");
      return;
    }
    if (!epinephrineAck || !accidentAck || !feeUndertaking || !terminationAck || !infoStorage || !cancellationAck || !illnessAck) {
      setError("Please read and agree to each acknowledgement and policy — they're required to register.");
      return;
    }
    if (marketing === null) {
      setError("Please tell us whether you'd like to hear about new services (yes or no).");
      return;
    }
    if (!signature1.trim() || !signedDate) {
      setError("Please sign (type your full name) and date the form.");
      return;
    }
    setSubmitting(true);
    try {
      await submitOnboarding(token, {
        guardian_first_name: firstName.trim(),
        guardian_surname: surname.trim(),
        email: email.trim(),
        phone: phone.trim(),
        guardian_id_number: idNumber.trim(),
        guardian2_name: g2Name.trim() || null,
        guardian2_id_number: g2Id.trim() || null,
        guardian2_email: g2Email.trim() || null,
        guardian2_phone: g2Phone.trim() || null,
        child_name: childName.trim(),
        child_dob: childDob,
        school: school.trim() || null,
        address: address.trim(),
        has_allergies: hasAllergies,
        allergy_details: allergyDetails.trim() || null,
        fee_undertaking: feeUndertaking,
        termination_60d_ack: terminationAck,
        info_storage_consent: infoStorage,
        marketing_opt_in: marketing,
        epinephrine_ack: epinephrineAck,
        accident_ack: accidentAck,
        cancellation_policy_ack: cancellationAck,
        illness_policy_ack: illnessAck,
        signature_guardian1: signature1.trim(),
        signature_guardian2: signature2.trim() || null,
        signed_date: signedDate,
      });
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
            ⚠ This onboarding link isn't valid any more. Please contact Learning 360° Foundation
            for a fresh link.
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
          <h1 className="l360-ob-title">
            {alreadySubmitted ? "Already completed" : "Thank you!"}
          </h1>
          <p className="l360-ob-intro">
            {alreadySubmitted
              ? "This onboarding form has already been submitted — there's nothing more to do. If any of your details change, just let us know."
              : "We've received your onboarding form and emailed you a confirmation. We look forward to welcoming you to Learning 360° Foundation."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="l360-ob-page">
      <form className="l360-ob-card" onSubmit={handleSubmit} noValidate>
        <Wordmark className="l360-login-wordmark" />
        <h1 className="l360-ob-title">Client onboarding form</h1>
        <p className="l360-ob-intro">{COPY.intro}</p>

        <Section title="Parent / Guardian 1" hint="Or the learner themselves, if of legal age.">
          <div className="l360-ob-grid">
            <Input id="ob-g1-first" label="First name" required value={firstName} onChange={(e) => setFirstName(e.target.value)} autoComplete="given-name" />
            <Input id="ob-g1-surname" label="Surname" required value={surname} onChange={(e) => setSurname(e.target.value)} autoComplete="family-name" />
          </div>
          <Input id="ob-g1-id" label="ID card number" required value={idNumber} onChange={(e) => setIdNumber(e.target.value)} />
          <div className="l360-ob-grid">
            <Input id="ob-g1-email" label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            <Input id="ob-g1-phone" label="Contact number" type="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" />
          </div>
        </Section>

        <Section title="Parent / Guardian 2" hint="Optional — leave blank if not applicable.">
          <div className="l360-ob-grid">
            <Input id="ob-g2-name" label="Name and surname" value={g2Name} onChange={(e) => setG2Name(e.target.value)} />
            <Input id="ob-g2-id" label="ID card number" value={g2Id} onChange={(e) => setG2Id(e.target.value)} />
          </div>
          <div className="l360-ob-grid">
            <Input id="ob-g2-email" label="Email" type="email" value={g2Email} onChange={(e) => setG2Email(e.target.value)} />
            <Input id="ob-g2-phone" label="Contact number" type="tel" value={g2Phone} onChange={(e) => setG2Phone(e.target.value)} />
          </div>
        </Section>

        <Section title="The learner">
          <div className="l360-ob-grid">
            <Input id="ob-child-name" label="Name and surname" required value={childName} onChange={(e) => setChildName(e.target.value)} />
            <Input id="ob-child-dob" label="Date of birth" type="date" required value={childDob} onChange={(e) => setChildDob(e.target.value)} />
          </div>
          <Input id="ob-school" label="School the learner attends" value={school} onChange={(e) => setSchool(e.target.value)} />
          <Textarea id="ob-address" label="Home address" required rows={2} value={address} onChange={(e) => setAddress(e.target.value)} autoComplete="street-address" />
        </Section>

        <Section title="Allergies">
          <YesNo legend="Does the learner have any allergies?" name="ob-allergies" value={hasAllergies} onChange={setHasAllergies} />
          {hasAllergies && (
            <Textarea
              id="ob-allergy-details"
              label="Please specify what they are"
              required
              rows={2}
              value={allergyDetails}
              onChange={(e) => setAllergyDetails(e.target.value)}
            />
          )}
          <AgreeCheck id="ob-epi" text={COPY.epinephrine} checked={epinephrineAck} onChange={setEpinephrineAck} />
          <AgreeCheck id="ob-accident" text={COPY.accident} checked={accidentAck} onChange={setAccidentAck} />
        </Section>

        <Section title="Fees">
          <AgreeCheck id="ob-fee" text={COPY.fee} checked={feeUndertaking} onChange={setFeeUndertaking} />
          <AgreeCheck id="ob-termination" text={COPY.termination} checked={terminationAck} onChange={setTerminationAck} />
        </Section>

        <Section title="Your information">
          <AgreeCheck id="ob-storage" text={COPY.infoStorage} checked={infoStorage} onChange={setInfoStorage} />
          <YesNo legend={COPY.marketing} name="ob-marketing" value={marketing} onChange={setMarketing} />
        </Section>

        <Section title="Policies">
          <p className="l360-ob-policy">
            <strong>Cancellation policy.</strong> {COPY.cancellation}
          </p>
          <AgreeCheck id="ob-cancellation" text="I agree to the cancellation policy." checked={cancellationAck} onChange={setCancellationAck} />
          <p className="l360-ob-policy">
            <strong>Illness policy.</strong> {COPY.illness}
          </p>
          <AgreeCheck id="ob-illness" text="I agree to the illness policy." checked={illnessAck} onChange={setIllnessAck} />
        </Section>

        <Section title="Signatures" hint="Typing your full name here counts as your signature.">
          <div className="l360-ob-grid">
            <Input
              id="ob-sig1"
              label="Signature of Parent/Guardian 1 / learner of legal age"
              required
              value={signature1}
              onChange={(e) => setSignature1(e.target.value)}
            />
            <Input id="ob-sig2" label="Signature of Parent/Guardian 2" value={signature2} onChange={(e) => setSignature2(e.target.value)} />
          </div>
          <Input id="ob-date" label="Date" type="date" required value={signedDate} onChange={(e) => setSignedDate(e.target.value)} />
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
          Learning 360° Foundation will not share any of the information provided with a third party.
        </p>
      </form>
    </div>
  );
}
