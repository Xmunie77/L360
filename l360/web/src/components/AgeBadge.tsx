// Small "Age N" box shown beside a learner's date-of-birth field
// (Simon, 04/09/2026). Live-updates as the date is typed; renders nothing
// for an empty, unparseable or future date. Under 1 year shows months.

export function ageFromDob(dob: string, today: Date = new Date()): string | null {
  if (!dob) return null;
  const d = new Date(dob + "T00:00:00");
  if (Number.isNaN(d.getTime()) || d > today) return null;
  let years = today.getFullYear() - d.getFullYear();
  const beforeBirthday =
    today.getMonth() < d.getMonth() ||
    (today.getMonth() === d.getMonth() && today.getDate() < d.getDate());
  if (beforeBirthday) years -= 1;
  if (years < 0) return null;
  if (years === 0) {
    let months = (today.getFullYear() - d.getFullYear()) * 12 + today.getMonth() - d.getMonth();
    if (today.getDate() < d.getDate()) months -= 1;
    return `${Math.max(months, 0)} mo`;
  }
  return String(years);
}

export function AgeBadge({ dob }: { dob: string | null | undefined }) {
  const age = ageFromDob(dob ?? "");
  if (age === null) return null;
  return (
    <span
      aria-label={`Current age ${age}`}
      style={{
        alignSelf: "flex-end",
        marginBottom: 22,
        padding: "6px 10px",
        border: "1px solid var(--l360-sand, #E4DAC9)",
        background: "var(--l360-cream, #FAF6EF)",
        fontSize: 13,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      Age {age}
    </span>
  );
}
