// Thin fetch wrapper around the l360 FastAPI backend (see ../../../api.py).
// Every call sends the session cookie (credentials: "include") — auth is
// cookie-based, not header-based. Non-2xx responses throw ApiError with the
// API's `detail` message so callers can show it inline (e.g. a 409 booking
// conflict) instead of a generic failure.

// --- types ---------------------------------------------------------------
// Mirrors the Pydantic schemas in ../../../schemas.py.

export interface Room {
  id: number;
  name: string;
  sort_order: number;
  active: boolean;
}

/** GET /api/educators returns UserOut shape, scoped to role === "educator". */
export interface Educator {
  id: number;
  email: string;
  full_name: string;
  role: string;
  level_id: number | null;
  active: boolean;
}

/** GET /api/clients returns the minimal ClientBrief shape — no notes/phone/DOB/observations. */
export interface Client {
  id: number;
  guardian_first_name: string;
  guardian_surname: string;
  child_name: string | null;
}

export type BookingStatus = "confirmed" | "cancelled" | "cancelled_late" | "completed" | "no_show";

export interface Booking {
  id: number;
  room_id: number;
  room_name: string;
  educator_id: number;
  educator_name: string;
  client_id: number;
  client_label: string;
  series_id: number | null;
  /** What's being billed — a named "session" item from the L360 price list. */
  service_type_id: number | null;
  service_type_name: string | null;
  start_utc: string;
  duration_minutes: number;
  status: BookingStatus;
  notes: string | null;
  created_by: number;
  created_at: string;
  cancelled_at: string | null;
}

export interface Me {
  id: number;
  email: string;
  full_name: string;
  role: string;
  level_id: number | null;
}

export type Duration = 60 | 90 | 120;

export interface BookingCreateInput {
  room_id: number;
  educator_id: number;
  client_id: number;
  service_type_id: number;
  start_utc: string;
  duration_minutes: Duration;
  notes?: string | null;
}

export interface BookingSeriesCreateInput {
  room_id: number;
  educator_id: number;
  client_id: number;
  service_type_id: number;
  weekday: number;
  local_time: string;
  duration_minutes: Duration;
  starts_on: string;
  ends_on: string;
  /** 1 = every week, 2 = every other week (fortnightly). */
  interval_weeks: 1 | 2;
  notes?: string | null;
}

export interface SkippedOccurrence {
  date: string;
  reason: string;
}

export interface BookingSeriesResult {
  series_id: number;
  created: Booking[];
  skipped: SkippedOccurrence[];
}

export interface BookingMoveInput {
  start_utc?: string;
  room_id?: number;
  duration_minutes?: Duration;
  service_type_id?: number;
  notes?: string | null;
}

export interface ListBookingsParams {
  start: string;
  end: string;
  roomId?: number;
  educatorId?: number;
  mine?: boolean;
}

// --- admin: reference data -------------------------------------------------
// Mirrors *In/*Out schemas for the /api/admin/* CRUD routes. All admin-only —
// a non-admin session gets a 403 ApiError, which screens should show as a
// plain "Admins only" message rather than a generic error.

export interface RoomInput {
  name: string;
  sort_order: number;
  active: boolean;
}

export interface EducatorLevel {
  id: number;
  name: string;
  sort_order: number;
  active: boolean;
}

export interface EducatorLevelInput {
  name: string;
  sort_order: number;
  active: boolean;
}

export type UserRole = "admin" | "educator";

/** GET /api/admin/users returns the full UserOut shape, including `active`. */
export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  level_id: number | null;
  active: boolean;
}

export interface UserCreateInput {
  email: string;
  full_name: string;
  role: UserRole;
  level_id?: number | null;
  /** Min 8 chars — enforced server-side too. */
  password: string;
}

export interface UserUpdateInput {
  full_name?: string;
  level_id?: number | null;
  active?: boolean;
  password?: string;
}

/** GET /api/admin/clients returns the full ClientOut shape (email/phone/notes/
 *  child DOB/observations), unlike the brief ClientBrief from /api/clients. */
export interface AdminClient {
  id: number;
  guardian_first_name: string;
  guardian_surname: string;
  email: string;
  phone: string | null;
  guardian_id_number: string | null;
  guardian2_name: string | null;
  guardian2_id_number: string | null;
  guardian2_email: string | null;
  guardian2_phone: string | null;
  child_name: string | null;
  child_dob: string | null;
  school: string | null;
  address: string | null;
  /** null = the allergies question hasn't been answered yet. */
  has_allergies: boolean | null;
  allergy_details: string | null;
  /** Onboarding notes on the child's needs (e.g. dyslexia, Down syndrome) — admins only. */
  observations: string | null;
  notes: string | null;
  active: boolean;
  /** "pending" | "submitted" | null (no onboarding form created yet). */
  onboarding_status: string | null;
}

export interface ClientInput {
  guardian_first_name: string;
  guardian_surname: string;
  email: string;
  phone?: string | null;
  guardian_id_number?: string | null;
  guardian2_name?: string | null;
  guardian2_id_number?: string | null;
  guardian2_email?: string | null;
  guardian2_phone?: string | null;
  child_name?: string | null;
  child_dob?: string | null;
  school?: string | null;
  address?: string | null;
  has_allergies?: boolean | null;
  allergy_details?: string | null;
  observations?: string | null;
  notes?: string | null;
  active: boolean;
}

/** GET /api/onboarding/:token — form status + whatever's already on record. */
export interface OnboardingPrefill {
  status: "pending" | "submitted";
  guardian_first_name: string;
  guardian_surname: string;
  email: string;
  phone: string | null;
  guardian_id_number: string | null;
  guardian2_name: string | null;
  guardian2_id_number: string | null;
  guardian2_email: string | null;
  guardian2_phone: string | null;
  child_name: string | null;
  child_dob: string | null;
  school: string | null;
  address: string | null;
  has_allergies: boolean | null;
  allergy_details: string | null;
}

export interface OnboardingSubmitInput {
  guardian_first_name: string;
  guardian_surname: string;
  email: string;
  phone: string;
  guardian_id_number: string;
  guardian2_name?: string | null;
  guardian2_id_number?: string | null;
  guardian2_email?: string | null;
  guardian2_phone?: string | null;
  child_name: string;
  child_dob: string;
  school?: string | null;
  address: string;
  has_allergies: boolean;
  allergy_details?: string | null;
  fee_undertaking: boolean;
  termination_60d_ack: boolean;
  info_storage_consent: boolean;
  marketing_opt_in: boolean;
  epinephrine_ack: boolean;
  accident_ack: boolean;
  cancellation_policy_ack: boolean;
  illness_policy_ack: boolean;
  signature_guardian1: string;
  signature_guardian2?: string | null;
  signed_date: string;
}

/** GET /api/admin/clients/:id/onboarding — the consent/signature record. */
export interface OnboardingAdmin {
  id: number;
  client_id: number;
  status: "pending" | "submitted";
  source: "app" | "google_form";
  link: string;
  sent_at: string | null;
  submitted_at: string | null;
  fee_undertaking: boolean | null;
  termination_60d_ack: boolean | null;
  info_storage_consent: boolean | null;
  marketing_opt_in: boolean | null;
  epinephrine_ack: boolean | null;
  accident_ack: boolean | null;
  cancellation_policy_ack: boolean | null;
  illness_policy_ack: boolean | null;
  signature_guardian1: string | null;
  signature_guardian2: string | null;
  signed_date: string | null;
}

/** Append-only — there is no update endpoint. A new row with a later
 *  valid_from supersedes the previous one for that (level, duration). */
export interface PriceListEntry {
  id: number;
  level_id: number;
  duration_minutes: Duration;
  client_price_cents: number;
  educator_rate_cents: number;
  valid_from: string;
}

export interface PriceListEntryInput {
  level_id: number;
  duration_minutes: Duration;
  client_price_cents: number;
  educator_rate_cents: number;
  valid_from: string;
}

export type ServiceTypeCategory = "session" | "additional_service";

/** A flat, named price for a session or service that doesn't fit the
 *  level+duration price list (e.g. "Onboarding Meeting", "Flashcards A4") —
 *  editable in place, unlike the append-only price list. */
export interface ServiceType {
  id: number;
  name: string;
  category: ServiceTypeCategory;
  client_price_cents: number;
  tutor_payment_cents: number;
  /** Whether this session occupies one of the foundation's own rooms — false
   *  for home/school visits, which happen off-site. Not applicable to
   *  additional services (never a calendar booking). */
  requires_room: boolean;
  sort_order: number;
  active: boolean;
}

export interface ServiceTypeInput {
  name: string;
  category: ServiceTypeCategory;
  client_price_cents: number;
  tutor_payment_cents: number;
  requires_room: boolean;
  sort_order: number;
  active: boolean;
}

export interface FacilityHours {
  id: number;
  weekday: number;
  open_time: string;
  close_time: string;
}

export interface FacilityHoursInput {
  weekday: number;
  /** "HH:MM:SS" */
  open_time: string;
  close_time: string;
}

export interface FacilityClosure {
  id: number;
  date: string;
  reason: string;
  room_id: number | null;
}

export interface FacilityClosureInput {
  date: string;
  reason: string;
  room_id?: number | null;
}

// --- billing -----------------------------------------------------------

export type InvoiceStatus = "draft" | "issued" | "paid" | "partially_paid" | "void";

export interface InvoiceLine {
  id: number;
  booking_id: number | null;
  description: string;
  unit_price_cents: number;
  quantity: number;
  amount_cents: number;
}

export interface Invoice {
  id: number;
  client_id: number;
  client_label: string;
  number: string | null;
  period_start: string;
  period_end: string;
  status: InvoiceStatus;
  total_cents: number;
  outstanding_cents: number;
  issued_at: string | null;
  due_date: string | null;
  notes: string | null;
  created_at: string;
}

export interface InvoiceDetail extends Invoice {
  lines: InvoiceLine[];
}

export interface BillingRunResult {
  created: Invoice[];
  /** Client ids the run had nothing billable for this period. */
  skipped_clients: number[];
}

export interface ListInvoicesParams {
  status?: InvoiceStatus;
  clientId?: number;
}

// --- payments / reconciliation ---------------------------------------------

export interface SyncResult {
  imported: number;
  matched: number;
  unmatched: number;
}

export interface BankTxn {
  id: number;
  external_id: string;
  txn_date: string;
  amount_cents: number;
  currency: string;
  reference: string | null;
  counterparty: string | null;
  payment_id: number | null;
}

export type PaymentMethod = "bank_transfer" | "cash";

export interface RecordPaymentInput {
  invoice_id: number;
  amount_cents: number;
  method: PaymentMethod;
  received_at: string;
  external_ref?: string | null;
}

export interface Payment {
  id: number;
  invoice_id: number;
  amount_cents: number;
  method: string;
  external_ref: string | null;
  received_at: string;
  match_status: string;
}

// --- error -----------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// --- request core ----------------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // response body wasn't JSON — fall back to statusText above
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined });
}

function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

function put<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

// --- auth --------------------------------------------------------------

export function login(email: string, password: string): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/api/login", { email, password });
}

export function logout(): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/api/logout");
}

export function getSession(): Promise<{ authed: boolean }> {
  return get<{ authed: boolean }>("/api/session");
}

export function getMe(): Promise<Me> {
  return get<Me>("/api/me");
}

export function forgotPassword(email: string): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/api/forgot-password", { email });
}

export function resetPassword(token: string, password: string): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/api/reset-password", { token, password });
}

// --- read-only lists -----------------------------------------------------

export function listRooms(): Promise<Room[]> {
  return get<Room[]>("/api/rooms");
}

export function listEducators(): Promise<Educator[]> {
  return get<Educator[]>("/api/educators");
}

/** Active "session" items from the L360 price list — what a booking can be
 *  billed against. Excludes "additional_service" items (flashcards, etc.),
 *  which are never calendar bookings. */
export function listSessionTypes(): Promise<ServiceType[]> {
  return get<ServiceType[]>("/api/session-types");
}

export function listClients(): Promise<Client[]> {
  return get<Client[]>("/api/clients");
}

// --- bookings --------------------------------------------------------------

export function listBookings(params: ListBookingsParams): Promise<Booking[]> {
  const qs = new URLSearchParams({ start: params.start, end: params.end });
  if (params.roomId !== undefined) qs.set("room_id", String(params.roomId));
  if (params.educatorId !== undefined) qs.set("educator_id", String(params.educatorId));
  if (params.mine !== undefined) qs.set("mine", String(params.mine));
  return get<Booking[]>(`/api/bookings?${qs.toString()}`);
}

export function createBooking(body: BookingCreateInput): Promise<Booking> {
  return post<Booking>("/api/bookings", body);
}

export function createBookingSeries(body: BookingSeriesCreateInput): Promise<BookingSeriesResult> {
  return post<BookingSeriesResult>("/api/bookings/series", body);
}

export interface NextAvailableRoom {
  room_id: number | null;
  room_name: string | null;
  start_utc: string | null;
  /** Set (with the room_* fields null) when nothing was found — tells
   *  "facility hours never configured" apart from "genuinely fully booked". */
  reason: "no_facility_hours" | "fully_booked" | null;
}

export function getNextAvailableRoom(durationMinutes: Duration = 60): Promise<NextAvailableRoom> {
  return get<NextAvailableRoom>(`/api/bookings/next-available?duration_minutes=${durationMinutes}`);
}

export function moveBooking(id: number, body: BookingMoveInput): Promise<Booking> {
  return patch<Booking>(`/api/bookings/${id}`, body);
}

export function cancelBooking(id: number): Promise<Booking> {
  return post<Booking>(`/api/bookings/${id}/cancel`);
}

// --- admin: rooms -----------------------------------------------------

export function adminListRooms(): Promise<Room[]> {
  return get<Room[]>("/api/admin/rooms");
}

export function adminCreateRoom(body: RoomInput): Promise<Room> {
  return post<Room>("/api/admin/rooms", body);
}

export function adminUpdateRoom(id: number, body: RoomInput): Promise<Room> {
  return put<Room>(`/api/admin/rooms/${id}`, body);
}

/** Deactivates the room — rooms are never hard-deleted. */
export function adminDeactivateRoom(id: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/api/admin/rooms/${id}`);
}

// --- admin: educator levels ------------------------------------------------

export function adminListEducatorLevels(): Promise<EducatorLevel[]> {
  return get<EducatorLevel[]>("/api/admin/educator-levels");
}

export function adminCreateEducatorLevel(body: EducatorLevelInput): Promise<EducatorLevel> {
  return post<EducatorLevel>("/api/admin/educator-levels", body);
}

export function adminUpdateEducatorLevel(id: number, body: EducatorLevelInput): Promise<EducatorLevel> {
  return put<EducatorLevel>(`/api/admin/educator-levels/${id}`, body);
}

// --- admin: users (educators/admins) ----------------------------------------

export function adminListUsers(): Promise<AdminUser[]> {
  return get<AdminUser[]>("/api/admin/users");
}

export function adminCreateUser(body: UserCreateInput): Promise<AdminUser> {
  return post<AdminUser>("/api/admin/users", body);
}

export function adminUpdateUser(id: number, body: UserUpdateInput): Promise<AdminUser> {
  return put<AdminUser>(`/api/admin/users/${id}`, body);
}

/** Deactivates the user — never hard-deleted (bookings/invoices reference it). */
export function adminDeactivateUser(id: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/api/admin/users/${id}`);
}

// --- admin: clients ----------------------------------------------------

export function adminListClients(): Promise<AdminClient[]> {
  return get<AdminClient[]>("/api/admin/clients");
}

export function adminGetClient(id: number): Promise<AdminClient> {
  return get<AdminClient>(`/api/admin/clients/${id}`);
}

export function adminCreateClient(body: ClientInput): Promise<AdminClient> {
  return post<AdminClient>("/api/admin/clients", body);
}

export function adminGetClientOnboarding(id: number): Promise<OnboardingAdmin | null> {
  return get<OnboardingAdmin | null>(`/api/admin/clients/${id}/onboarding`);
}

export interface EmailSettings {
  host: string;
  port: number;
  user: string;
  email_from: string;
  /** Whether a password is stored (DB or env) — the password itself is never returned. */
  password_set: boolean;
}

export interface EmailSettingsInput {
  host: string;
  port: number;
  user: string;
  email_from: string;
  /** Omit or send blank to keep the stored password. */
  password?: string | null;
}

export function adminGetEmailSettings(): Promise<EmailSettings> {
  return get<EmailSettings>("/api/admin/email-settings");
}

export function adminSaveEmailSettings(body: EmailSettingsInput): Promise<EmailSettings> {
  return put<EmailSettings>("/api/admin/email-settings", body);
}

export function adminTestEmail(): Promise<{ ok: boolean; detail: string }> {
  return post<{ ok: boolean; detail: string }>("/api/admin/email-settings/test");
}

export function adminSendOnboarding(id: number): Promise<OnboardingAdmin> {
  return post<OnboardingAdmin>(`/api/admin/clients/${id}/onboarding/send`);
}

export function getOnboarding(token: string): Promise<OnboardingPrefill> {
  return get<OnboardingPrefill>(`/api/onboarding/${encodeURIComponent(token)}`);
}

export function submitOnboarding(token: string, body: OnboardingSubmitInput): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>(`/api/onboarding/${encodeURIComponent(token)}`, body);
}

export function adminUpdateClient(id: number, body: ClientInput): Promise<AdminClient> {
  return put<AdminClient>(`/api/admin/clients/${id}`, body);
}

// --- admin: price list (append-only) ----------------------------------------

export function adminListPriceList(): Promise<PriceListEntry[]> {
  return get<PriceListEntry[]>("/api/admin/price-list");
}

export function adminCreatePriceEntry(body: PriceListEntryInput): Promise<PriceListEntry> {
  return post<PriceListEntry>("/api/admin/price-list", body);
}

// --- admin: service types (named sessions/additional services) --------------

export function adminListServiceTypes(): Promise<ServiceType[]> {
  return get<ServiceType[]>("/api/admin/service-types");
}

export function adminCreateServiceType(body: ServiceTypeInput): Promise<ServiceType> {
  return post<ServiceType>("/api/admin/service-types", body);
}

export function adminUpdateServiceType(id: number, body: ServiceTypeInput): Promise<ServiceType> {
  return put<ServiceType>(`/api/admin/service-types/${id}`, body);
}

export function adminDeactivateServiceType(id: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/api/admin/service-types/${id}`);
}

// --- admin: facility hours / closures ---------------------------------------

export function adminListFacilityHours(): Promise<FacilityHours[]> {
  return get<FacilityHours[]>("/api/admin/facility-hours");
}

/** Upsert by weekday. */
export function adminUpsertFacilityHours(body: FacilityHoursInput): Promise<FacilityHours> {
  return put<FacilityHours>("/api/admin/facility-hours", body);
}

export function adminListClosures(): Promise<FacilityClosure[]> {
  return get<FacilityClosure[]>("/api/admin/closures");
}

export function adminCreateClosure(body: FacilityClosureInput): Promise<FacilityClosure> {
  return post<FacilityClosure>("/api/admin/closures", body);
}

export function adminDeleteClosure(id: number): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/api/admin/closures/${id}`);
}

// --- billing -------------------------------------------------------------

export function runBilling(periodStart: string, periodEnd: string): Promise<BillingRunResult> {
  return post<BillingRunResult>("/api/admin/billing/run", { period_start: periodStart, period_end: periodEnd });
}

export function listInvoices(params: ListInvoicesParams = {}): Promise<Invoice[]> {
  const qs = new URLSearchParams();
  if (params.status !== undefined) qs.set("status", params.status);
  if (params.clientId !== undefined) qs.set("client_id", String(params.clientId));
  const suffix = qs.toString();
  return get<Invoice[]>(`/api/admin/invoices${suffix ? `?${suffix}` : ""}`);
}

export function getInvoice(id: number): Promise<InvoiceDetail> {
  return get<InvoiceDetail>(`/api/admin/invoices/${id}`);
}

export function issueInvoice(id: number): Promise<Invoice> {
  return post<Invoice>(`/api/admin/invoices/${id}/issue`);
}

// --- payments / reconciliation -----------------------------------------

/** 409s with detail "REVOLUT_API_TOKEN is not set" when Revolut isn't
 *  connected yet — callers should show that inline, not as an error toast. */
export function syncPayments(): Promise<SyncResult> {
  return post<SyncResult>("/api/admin/payments/sync");
}

export function listUnmatchedTxns(): Promise<BankTxn[]> {
  return get<BankTxn[]>("/api/admin/payments/unmatched");
}

export function manualMatchPayment(bankTxnId: number, invoiceId: number): Promise<Payment> {
  return post<Payment>("/api/admin/payments/manual-match", { bank_txn_id: bankTxnId, invoice_id: invoiceId });
}

export function recordPayment(body: RecordPaymentInput): Promise<Payment> {
  return post<Payment>("/api/admin/payments/record", body);
}

// --- statements / reports / calendar feed ---------------------------------

export interface StatementInvoiceLine {
  id: number;
  number: string | null;
  status: string;
  total_cents: number;
  issued_at: string | null;
}

export interface StatementPaymentLine {
  id: number;
  amount_cents: number;
  method: string;
  received_at: string;
}

export interface ClientStatement {
  client_id: number;
  client_label: string;
  period_start: string;
  period_end: string;
  opening_balance_cents: number;
  invoices: StatementInvoiceLine[];
  payments: StatementPaymentLine[];
  closing_balance_cents: number;
}

export interface SummarySessionLine {
  booking_id: number;
  local_date: string;
  client_label: string;
  duration_minutes: number;
  status: string;
  rate_cents: number;
}

export interface EducatorSummary {
  educator_id: number;
  educator_name: string;
  period_start: string;
  period_end: string;
  sessions: SummarySessionLine[];
  total_payable_cents: number;
}

export interface RoomUtilisation {
  room_id: number;
  room_name: string;
  session_count: number;
  booked_minutes: number;
}

export interface CalendarToken {
  token: string;
  feed_path: string;
}

export function getClientStatement(clientId: number, periodStart: string, periodEnd: string): Promise<ClientStatement> {
  const qs = new URLSearchParams({ period_start: periodStart, period_end: periodEnd });
  return get<ClientStatement>(`/api/admin/statements/client/${clientId}?${qs.toString()}`);
}

export function getEducatorSummary(educatorId: number, periodStart: string, periodEnd: string): Promise<EducatorSummary> {
  const qs = new URLSearchParams({ period_start: periodStart, period_end: periodEnd });
  return get<EducatorSummary>(`/api/statements/educator/${educatorId}/summary?${qs.toString()}`);
}

export function getUtilisationReport(periodStart: string, periodEnd: string): Promise<RoomUtilisation[]> {
  const qs = new URLSearchParams({ period_start: periodStart, period_end: periodEnd });
  return get<RoomUtilisation[]>(`/api/admin/reports/utilisation?${qs.toString()}`);
}

export function getMyCalendarToken(): Promise<CalendarToken | null> {
  return get<CalendarToken | null>("/api/me/calendar-token");
}

export function createOrRotateCalendarToken(): Promise<CalendarToken> {
  return post<CalendarToken>("/api/me/calendar-token");
}

export function revokeCalendarToken(): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>("/api/me/calendar-token");
}
