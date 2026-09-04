import { useEffect, useMemo, useState, type CSSProperties, type FormEvent, type MouseEvent } from "react";
import { Modal } from "../components/Modal";
import { Button, Card, Input, Money, Select, StatusBadge, Textarea } from "../ui/ui";
import {
  ApiError,
  cancelBooking,
  voidInvoice,
  createBooking,
  createBookingSeries,
  getNextAvailableRoom,
  listBookings,
  listClients,
  listEducators,
  listRooms,
  listSessionTypes,
  moveBooking,
  type Booking,
  type Client,
  type Duration,
  type Educator,
  type Me,
  type NextAvailableRoom,
  type Room,
  type ServiceType,
  type SkippedOccurrence,
} from "../api/client";
import { ConfirmSessionFlow, LateCancelModal, VoidInvoiceModal, type OutcomePreview } from "../components/ConfirmSessionFlow";
import { billingBadgeProps, statusBadgeProps } from "../domain/status";
import {
  addDays,
  combineDateTime,
  dayBoundsISO,
  formatBookingWhen,
  formatHourLabel,
  localDateStr,
  localHourFraction,
  mondayBasedWeekday,
  rangeBoundsISO,
  startOfWeek,
  toDateInputValue,
  todayStr,
  toTimeInputValue,
  weekDates,
} from "../domain/datetime";
import { layoutLanes } from "../domain/lanes";
import { MOBILE_QUERY, useMediaQuery } from "../hooks/useMediaQuery";

const REPEAT_OPTIONS = [
  { value: "none", label: "Doesn't repeat" },
  { value: "weekly", label: "Weekly" },
  { value: "fortnightly", label: "Every 2 weeks" },
];

const DEFAULT_START_HOUR = 8;
const DEFAULT_END_HOUR = 19;
const HOUR_PX = 60;
const DURATION_OPTIONS: { value: string; label: string }[] = [
  { value: "60", label: "60 minutes" },
  { value: "90", label: "90 minutes" },
  { value: "120", label: "120 minutes" },
];

interface NewBookingDraft {
  roomId: number;
  time: string;
  /** The clicked column's OWN day — in week view this isn't the toolbar date. */
  date: string;
  /** Pre-selected educator, when the column represents one. */
  educatorId?: number;
}

// A scheduler is time x room x person squeezed into a 2-D grid: time is always
// the vertical axis and the user picks what the columns are (04/09/2026).
//   day + rooms      -> a column per room (the original view)
//   day + educators  -> a column per educator: who's free today
//   week + rooms     -> Mon-Sun for one room, or all rooms packed into lanes
//   week + educators -> Mon-Sun for one educator
type CalRange = "day" | "week";
type CalGroupBy = "rooms" | "educators";

/** One grid column. `date` is the day it represents — in day view every
 * column shares the toolbar's date; in week view each column is its own. */
interface CalColumn {
  key: string;
  label: string;
  sub?: string;
  date: string;
  roomId?: number;
  educatorId?: number;
  isToday?: boolean;
}

const ALL_ROOMS = "all";
const VIEW_STORAGE_KEY = "l360-calendar-view";

interface StoredView {
  range: CalRange;
  groupBy: CalGroupBy;
  roomChoice: string;
  educatorChoice: string;
}

function loadStoredView(): Partial<StoredView> {
  // Private-mode Safari throws on access, and a stale/garbled value must
  // never stop the calendar rendering — fall back to the defaults.
  try {
    const raw = window.localStorage.getItem(VIEW_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Partial<StoredView>) : {};
  } catch {
    return {};
  }
}

function saveStoredView(view: StoredView) {
  try {
    window.localStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify(view));
  } catch {
    /* not worth surfacing — the view just won't be remembered */
  }
}

// Day view: one column per active room, a time axis down the left, sessions
// rendered as positioned blocks. Click an empty column to book, click a
// block to see/cancel/move it. Plain CSS grid + absolute positioning — no
// calendar library.
export function Calendar({ me }: { me: Me | null }) {
  const stored = useMemo(loadStoredView, []);
  const [date, setDate] = useState<string>(todayStr());
  const [range, setRange] = useState<CalRange>(stored.range === "week" ? "week" : "day");
  const [groupBy, setGroupBy] = useState<CalGroupBy>(stored.groupBy === "educators" ? "educators" : "rooms");
  // Which room/educator the week view is showing. "" = not chosen yet, filled
  // in from the reference data once it loads.
  const [roomChoice, setRoomChoice] = useState<string>(stored.roomChoice ?? ALL_ROOMS);
  const [educatorChoice, setEducatorChoice] = useState<string>(stored.educatorChoice ?? "");
  const isMobile = useMediaQuery(MOBILE_QUERY);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [educators, setEducators] = useState<Educator[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [sessionTypes, setSessionTypes] = useState<ServiceType[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [newBookingDraft, setNewBookingDraft] = useState<NewBookingDraft | null>(null);
  const [selectedBooking, setSelectedBooking] = useState<Booking | null>(null);
  const [nextAvailable, setNextAvailable] = useState<NextAvailableRoom | undefined>(undefined);

  // Reference data — fetched once.
  useEffect(() => {
    Promise.all([listRooms(), listEducators(), listClients(), listSessionTypes()])
      .then(([r, e, c, st]) => {
        setRooms(r);
        setEducators(e);
        setClients(c);
        setSessionTypes(st);
      })
      .catch((err) => {
        setLoadError(err instanceof ApiError ? err.detail : "Couldn't load rooms, educators, learners or session types.");
      });
  }, []);

  function refreshNextAvailable() {
    // A fetch error here just leaves the bar absent (undefined) rather
    // than showing a fabricated "nothing available" reason.
    getNextAvailableRoom()
      .then(setNextAvailable)
      .catch(() => {});
  }

  useEffect(() => {
    refreshNextAvailable();
  }, []);

  function bookNextAvailable() {
    if (!nextAvailable?.room_id || !nextAvailable.start_utc) return;
    const start = new Date(nextAvailable.start_utc);
    const day = toDateInputValue(start);
    setDate(day);
    setNewBookingDraft({
      roomId: nextAvailable.room_id,
      time: toTimeInputValue(nextAvailable.start_utc),
      date: day,
    });
  }

  async function refreshBookings() {
    setLoading(true);
    setLoadError(null);
    try {
      // One fetch for the whole visible range; the room/educator picker then
      // filters in memory, so switching resource within a week is instant.
      const { startISO, endISO } =
        range === "week" ? rangeBoundsISO(startOfWeek(date), 7) : dayBoundsISO(date);
      const rows = await listBookings({ start: startISO, end: endISO });
      setBookings(rows);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.detail : "Couldn't load bookings for this period.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshBookings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date, range]);

  const activeRooms = useMemo(() => rooms.filter((r) => r.active), [rooms]);

  // Default the educator picker to the viewer once educators have loaded —
  // an educator opening a week almost always wants their own.
  useEffect(() => {
    if (educatorChoice || educators.length === 0) return;
    const self = me && educators.some((e) => e.id === me.id) ? me.id : educators[0].id;
    setEducatorChoice(String(self));
  }, [educators, me, educatorChoice]);

  // A stored room/educator that has since been deactivated must not leave the
  // grid mysteriously empty.
  useEffect(() => {
    if (roomChoice !== ALL_ROOMS && activeRooms.length > 0 && !activeRooms.some((r) => String(r.id) === roomChoice)) {
      setRoomChoice(ALL_ROOMS);
    }
  }, [activeRooms, roomChoice]);
  useEffect(() => {
    if (educatorChoice && educators.length > 0 && !educators.some((e) => String(e.id) === educatorChoice)) {
      setEducatorChoice(String(educators[0].id));
    }
  }, [educators, educatorChoice]);

  useEffect(() => {
    saveStoredView({ range, groupBy, roomChoice, educatorChoice });
  }, [range, groupBy, roomChoice, educatorChoice]);

  const today = todayStr();

  // In week view the picker narrows the fetched week to one resource (or, for
  // rooms, optionally all of them).
  const visibleBookings = useMemo(() => {
    if (range !== "week") return bookings;
    if (groupBy === "rooms") {
      return roomChoice === ALL_ROOMS
        ? bookings
        : bookings.filter((b) => String(b.room_id) === roomChoice);
    }
    return bookings.filter((b) => String(b.educator_id) === educatorChoice);
  }, [bookings, range, groupBy, roomChoice, educatorChoice]);

  const columns: CalColumn[] = useMemo(() => {
    if (range === "week") {
      return weekDates(date).map((d) => {
        const [, m, day] = d.split("-");
        return {
          key: d,
          label: new Date(`${d}T00:00:00`).toLocaleDateString("en-GB", { weekday: "short" }),
          sub: `${day}/${m}`,
          date: d,
          roomId: groupBy === "rooms" && roomChoice !== ALL_ROOMS ? Number(roomChoice) : undefined,
          educatorId: groupBy === "educators" ? Number(educatorChoice) : undefined,
          isToday: d === today,
        };
      });
    }
    if (groupBy === "educators") {
      return educators.map((e) => ({
        key: `e${e.id}`,
        label: e.full_name,
        date,
        educatorId: e.id,
        isToday: date === today,
      }));
    }
    return activeRooms.map((r) => ({
      key: `r${r.id}`,
      label: r.name,
      date,
      roomId: r.id,
      isToday: date === today,
    }));
  }, [range, groupBy, date, today, activeRooms, educators, roomChoice, educatorChoice]);

  /** Which column a booking belongs in — the whole point of the generalised grid. */
  function columnKeyOf(b: Booking): string {
    if (range === "week") return localDateStr(b.start_utc);
    return groupBy === "educators" ? `e${b.educator_id}` : `r${b.room_id}`;
  }

  const byColumn = useMemo(() => {
    const map = new Map<string, Booking[]>();
    for (const b of visibleBookings) {
      const key = columnKeyOf(b);
      const list = map.get(key);
      if (list) list.push(b);
      else map.set(key, [b]);
    }
    return map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleBookings, range, groupBy]);

  const { startHour, endHour } = useMemo(() => {
    let start = DEFAULT_START_HOUR;
    let end = DEFAULT_END_HOUR;
    for (const b of visibleBookings) {
      const s = localHourFraction(b.start_utc);
      const e = s + b.duration_minutes / 60;
      if (s < start) start = Math.floor(s);
      if (e > end) end = Math.ceil(e);
    }
    return { startHour: start, endHour: end };
  }, [visibleBookings]);

  const totalHours = endHour - startHour;
  const gridHeight = totalHours * HOUR_PX;
  const hourMarks = useMemo(() => {
    const marks: number[] = [];
    for (let h = startHour; h <= endHour; h++) marks.push(h);
    return marks;
  }, [startHour, endHour]);

  // The current-time line only appears on a column that IS today; ticking
  // once a minute is enough for a 60px-per-hour grid.
  const [nowFraction, setNowFraction] = useState(() => {
    const n = new Date();
    return n.getHours() + n.getMinutes() / 60;
  });
  useEffect(() => {
    const id = window.setInterval(() => {
      const n = new Date();
      setNowFraction(n.getHours() + n.getMinutes() / 60);
    }, 60_000);
    return () => window.clearInterval(id);
  }, []);

  function step(direction: -1 | 1) {
    setDate((d) => addDays(d, direction * (range === "week" ? 7 : 1)));
  }

  /** A column may know its room (day-by-room, or a week pinned to one room);
   * otherwise the modal's room select decides, pre-filled with the first. */
  function draftFor(column: CalColumn, time: string): NewBookingDraft {
    return {
      roomId: column.roomId ?? activeRooms[0]?.id ?? 0,
      time,
      date: column.date,
      educatorId: column.educatorId,
    };
  }

  function handleColumnClick(e: MouseEvent<HTMLDivElement>, column: CalColumn) {
    const rect = e.currentTarget.getBoundingClientRect();
    const offsetY = e.clientY - rect.top;
    let hour = startHour + offsetY / HOUR_PX;
    // Snap to the nearest 15 minutes and keep it inside the visible range.
    hour = Math.round(hour * 4) / 4;
    hour = Math.min(Math.max(hour, startHour), endHour - 0.25);
    setNewBookingDraft(draftFor(column, formatHourLabel(hour)));
  }

  return (
    <>
      <Card>
        <div className="l360-cal-toolbar">
          <Input
            id="cal-date"
            label={range === "week" ? "Week of" : "Day"}
            type="date"
            value={range === "week" ? startOfWeek(date) : date}
            onChange={(e) => setDate(e.target.value)}
          />
          <div className="l360-cal-stepper">
            <Button type="button" variant="secondary" aria-label={range === "week" ? "Previous week" : "Previous day"} onClick={() => step(-1)}>
              ‹
            </Button>
            <Button type="button" variant="secondary" onClick={() => setDate(todayStr())}>
              Today
            </Button>
            <Button type="button" variant="secondary" aria-label={range === "week" ? "Next week" : "Next day"} onClick={() => step(1)}>
              ›
            </Button>
          </div>

          <div className="l360-cal-switch" role="tablist" aria-label="Range">
            {(["day", "week"] as CalRange[]).map((r) => (
              <Button
                key={r}
                type="button"
                role="tab"
                aria-selected={range === r}
                variant={range === r ? "primary" : "secondary"}
                onClick={() => setRange(r)}
              >
                {r === "day" ? "Day" : "Week"}
              </Button>
            ))}
          </div>

          <div className="l360-cal-switch" role="tablist" aria-label="Group by">
            {(["rooms", "educators"] as CalGroupBy[]).map((g) => (
              <Button
                key={g}
                type="button"
                role="tab"
                aria-selected={groupBy === g}
                variant={groupBy === g ? "primary" : "secondary"}
                onClick={() => setGroupBy(g)}
              >
                {g === "rooms" ? "Rooms" : "Educators"}
              </Button>
            ))}
          </div>

          {range === "week" && groupBy === "rooms" && (
            <Select
              id="cal-room-choice"
              label="Showing"
              value={roomChoice}
              onChange={(e) => setRoomChoice(e.target.value)}
              options={[
                { value: ALL_ROOMS, label: "All rooms" },
                ...activeRooms.map((r) => ({ value: String(r.id), label: r.name })),
              ]}
            />
          )}
          {range === "week" && groupBy === "educators" && (
            <Select
              id="cal-educator-choice"
              label="Showing"
              value={educatorChoice}
              onChange={(e) => setEducatorChoice(e.target.value)}
              options={educators.map((e) => ({ value: String(e.id), label: e.full_name }))}
            />
          )}
        </div>

        {nextAvailable !== undefined && (
          <div className="l360-cal-next-available">
            {nextAvailable.room_id && nextAvailable.room_name && nextAvailable.start_utc ? (
              <>
                <span className="l360-cal-next-text">
                  <span>
                    Next available: <strong>{nextAvailable.room_name}</strong>
                  </span>
                  <span className="l360-cal-next-when">{formatBookingWhen(nextAvailable.start_utc)}</span>
                </span>
                <Button type="button" onClick={bookNextAvailable}>
                  Book
                </Button>
              </>
            ) : (
              <span>No rooms free in the next two weeks.</span>
            )}
          </div>
        )}

        {loadError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {loadError}
          </div>
        )}

        {!loadError && activeRooms.length === 0 && !loading && (
          <p className="l360-empty">No active rooms configured yet.</p>
        )}

        {columns.length === 0 && activeRooms.length > 0 && !loading && (
          <p className="l360-empty">No educators to show yet.</p>
        )}

        {/* A 7-column week needs ~1200px; on a phone it becomes an agenda
            list instead, which is what every mature calendar app does. */}
        {columns.length > 0 && isMobile && range === "week" ? (
          <CalendarAgenda
            columns={columns}
            byColumn={byColumn}
            groupBy={groupBy}
            onSelect={setSelectedBooking}
          />
        ) : columns.length > 0 ? (
          <div className="l360-cal-grid-wrap">
            <div
              className="l360-cal-grid"
              style={{
                gridTemplateColumns: `72px repeat(${columns.length}, minmax(140px, 1fr))`,
                minWidth: 72 + columns.length * 140,
              }}
            >
              <div className="l360-cal-corner" aria-hidden="true" />
              {columns.map((col) => (
                <div
                  key={col.key}
                  className={col.isToday ? "l360-cal-room-head l360-cal-head-today" : "l360-cal-room-head"}
                >
                  {col.label}
                  {col.sub && <span className="l360-cal-head-sub">{col.sub}</span>}
                </div>
              ))}

              <div className="l360-cal-time-col" style={{ height: gridHeight }}>
                {hourMarks.map((h) => (
                  <span
                    key={h}
                    className="l360-cal-time-mark"
                    style={{ top: (h - startHour) * HOUR_PX }}
                  >
                    {formatHourLabel(h)}
                  </span>
                ))}
              </div>

              {columns.map((col) => {
                const colBookings = byColumn.get(col.key) ?? [];
                // Overlapping sessions share the column width instead of
                // hiding each other (the pre-04/09/2026 behaviour).
                const lanes = layoutLanes(
                  colBookings.map((b) => {
                    const s = localHourFraction(b.start_utc);
                    return { start: s, end: s + b.duration_minutes / 60 };
                  }),
                );
                const showNow = col.isToday && nowFraction >= startHour && nowFraction <= endHour;
                return (
                  <div
                    key={col.key}
                    className="l360-cal-room-col"
                    style={{ height: gridHeight, "--l360-cal-hour-h": `${HOUR_PX}px` } as CSSProperties}
                    onClick={(e) => handleColumnClick(e, col)}
                    role="button"
                    tabIndex={0}
                    aria-label={`New booking — ${col.label}${col.sub ? ` ${col.sub}` : ""}`}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setNewBookingDraft(draftFor(col, formatHourLabel(startHour)));
                      }
                    }}
                  >
                    {showNow && (
                      <div
                        className="l360-cal-now-line"
                        style={{ top: (nowFraction - startHour) * HOUR_PX }}
                        aria-hidden="true"
                      />
                    )}
                    {colBookings.map((b, i) => {
                      const top = (localHourFraction(b.start_utc) - startHour) * HOUR_PX;
                      const height = Math.max((b.duration_minutes / 60) * HOUR_PX, 24);
                      const { variant, label } = statusBadgeProps(b);
                      const { lane, laneCount } = lanes[i];
                      const width = 100 / laneCount;
                      return (
                        <button
                          key={b.id}
                          type="button"
                          className={`l360-cal-block l360-cal-block-${b.status}`}
                          style={{
                            top,
                            height,
                            left: `calc(${lane * width}% + 2px)`,
                            width: `calc(${width}% - 4px)`,
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedBooking(b);
                          }}
                        >
                          <span className="l360-cal-block-title">
                            {groupBy === "educators" && range === "day" ? b.client_label : b.educator_name}
                          </span>
                          <span className="l360-cal-block-sub">
                            {groupBy === "educators" && range === "day" ? b.room_name : b.client_label}
                          </span>
                          <span className="l360-cal-block-sub">
                            {/* In an all-rooms week the room is the one thing
                                the column can't tell you. */}
                            {range === "week" && groupBy === "rooms" && roomChoice === ALL_ROOMS
                              ? b.room_name
                              : variant === "success"
                                ? ""
                                : label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
      </Card>

      {newBookingDraft && (
        <NewBookingModal
          draft={newBookingDraft}
          date={newBookingDraft.date}
          rooms={activeRooms}
          educators={educators}
          clients={clients}
          sessionTypes={sessionTypes}
          me={me}
          onClose={() => setNewBookingDraft(null)}
          onCreated={() => {
            setNewBookingDraft(null);
            refreshBookings();
            refreshNextAvailable();
          }}
        />
      )}

      {selectedBooking && (
        <BookingDetailModal
          booking={selectedBooking}
          me={me}
          onClose={() => setSelectedBooking(null)}
          onChanged={() => {
            setSelectedBooking(null);
            refreshBookings();
            refreshNextAvailable();
          }}
        />
      )}
    </>
  );
}

// --- mobile agenda ---------------------------------------------------------

/** The week view on a phone: a heading per day, then that day's sessions as
 * tappable rows. A 7-column grid needs ~1200px, so below 820px this replaces
 * it rather than asking for three screens of sideways scrolling. */
function CalendarAgenda({
  columns,
  byColumn,
  groupBy,
  onSelect,
}: {
  columns: CalColumn[];
  byColumn: Map<string, Booking[]>;
  groupBy: CalGroupBy;
  onSelect: (b: Booking) => void;
}) {
  const hasAny = columns.some((c) => (byColumn.get(c.key) ?? []).length > 0);
  if (!hasAny) {
    return <p className="l360-empty">No sessions this week.</p>;
  }
  return (
    <div className="l360-cal-agenda">
      {columns.map((col) => {
        const rows = (byColumn.get(col.key) ?? [])
          .slice()
          .sort((a, b) => a.start_utc.localeCompare(b.start_utc));
        return (
          <section key={col.key} className="l360-cal-agenda-day">
            <h3 className={col.isToday ? "l360-cal-agenda-head l360-cal-head-today" : "l360-cal-agenda-head"}>
              {col.label} {col.sub}
            </h3>
            {rows.length === 0 ? (
              <p className="l360-cal-agenda-empty">—</p>
            ) : (
              rows.map((b) => {
                const { variant, label } = statusBadgeProps(b);
                return (
                  <button
                    key={b.id}
                    type="button"
                    className={`l360-cal-agenda-row l360-cal-block-${b.status}`}
                    onClick={() => onSelect(b)}
                  >
                    <span className="l360-cal-agenda-time">{toTimeInputValue(b.start_utc)}</span>
                    <span className="l360-cal-agenda-main">
                      <span className="l360-cal-block-title">{b.client_label}</span>
                      <span className="l360-cal-block-sub">
                        {groupBy === "educators" ? b.room_name : b.educator_name} · {b.duration_minutes} min
                      </span>
                    </span>
                    {variant !== "success" && <span className="l360-cal-agenda-status">{label}</span>}
                  </button>
                );
              })
            )}
          </section>
        );
      })}
    </div>
  );
}

// --- New booking modal -----------------------------------------------------

interface NewBookingModalProps {
  draft: NewBookingDraft;
  date: string;
  rooms: Room[];
  educators: Educator[];
  clients: Client[];
  sessionTypes: ServiceType[];
  me: Me | null;
  onClose: () => void;
  onCreated: () => void;
}

function NewBookingModal({ draft, date, rooms, educators, clients, sessionTypes, me, onClose, onCreated }: NewBookingModalProps) {
  const [roomId, setRoomId] = useState(String(draft.roomId));
  // If the person booking is themselves a bookable educator, default the
  // field to them — they're usually booking their own session — but leave
  // it editable (an admin/educator can still book on someone else's behalf).
  const [educatorId, setEducatorId] = useState(
    // A click in an educator's own column means that educator; otherwise
    // default to the person booking, if they deliver sessions themselves.
    draft.educatorId
      ? String(draft.educatorId)
      : me && educators.some((e) => e.id === me.id)
        ? String(me.id)
        : "",
  );
  const [clientId, setClientId] = useState("");
  const [sessionTypeId, setSessionTypeId] = useState("");
  const [time, setTime] = useState(draft.time);
  const [duration, setDuration] = useState("60");
  const [notes, setNotes] = useState("");
  const [repeat, setRepeat] = useState("none");
  const [repeatEndsOn, setRepeatEndsOn] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [skipped, setSkipped] = useState<SkippedOccurrence[] | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    // Per-field errors: mark exactly what's missing and put focus there,
    // instead of one lumped sentence at the top (04/09/2026 UI audit).
    const errs: Record<string, string> = {};
    if (!educatorId) errs.educator = "Choose an educator.";
    if (!clientId) errs.client = "Choose a learner.";
    if (!sessionTypeId) errs.sessionType = "Choose a session type.";
    if (repeat !== "none" && !repeatEndsOn) errs.repeatEndsOn = "Choose a date to repeat until.";
    setFieldErrors(errs);
    if (Object.keys(errs).length > 0) {
      const firstId = errs.educator ? "nb-educator" : errs.client ? "nb-client" : errs.sessionType ? "nb-session-type" : "nb-repeat-ends";
      document.getElementById(firstId)?.focus();
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      if (repeat === "none") {
        await createBooking({
          room_id: Number(roomId),
          educator_id: Number(educatorId),
          client_id: Number(clientId),
          service_type_id: Number(sessionTypeId),
          start_utc: combineDateTime(date, time),
          duration_minutes: Number(duration) as Duration,
          notes: notes || null,
        });
        onCreated();
      } else {
        const result = await createBookingSeries({
          room_id: Number(roomId),
          educator_id: Number(educatorId),
          client_id: Number(clientId),
          service_type_id: Number(sessionTypeId),
          weekday: mondayBasedWeekday(date),
          local_time: `${time}:00`,
          duration_minutes: Number(duration) as Duration,
          starts_on: date,
          ends_on: repeatEndsOn,
          interval_weeks: repeat === "fortnightly" ? 2 : 1,
          notes: notes || null,
        });
        if (result.skipped.length > 0) {
          // Some occurrences conflicted — show what happened instead of
          // silently closing, so the admin knows which dates need a look.
          setSkipped(result.skipped);
        } else {
          onCreated();
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't create the booking. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (skipped) {
    return (
      <Modal onClose={onClose}>
          <Card eyebrow="Scheduling" title="Repeating booking created">
            <p style={{ marginBottom: 12 }}>
              {skipped.length} of the occurrences couldn't be booked — the room or educator was already busy:
            </p>
            <ul style={{ marginBottom: 16 }}>
              {skipped.map((s) => (
                <li key={s.date}>
                  {s.date} — {s.reason}
                </li>
              ))}
            </ul>
            <Button type="button" onClick={onCreated}>
              Done
            </Button>
          </Card>
      </Modal>
    );
  }

  return (
    <Modal onClose={onClose} dirty={clientId !== "" || sessionTypeId !== "" || notes !== ""}>
        <Card eyebrow="Scheduling" title="New booking">
          <form onSubmit={handleSubmit} noValidate>
            {error && (
              <div className="l360-alert l360-alert-danger" role="alert">
                ⚠ {error}
              </div>
            )}

            <Select
              id="nb-room"
              label="Room"
              required
              value={roomId}
              onChange={(e) => setRoomId(e.target.value)}
              options={rooms.map((r) => ({ value: String(r.id), label: r.name }))}
            />
            <Select
              id="nb-educator"
              error={fieldErrors.educator}
              label="Educator"
              required
              placeholder="Choose an educator"
              value={educatorId}
              onChange={(e) => setEducatorId(e.target.value)}
              options={educators.map((e) => ({ value: String(e.id), label: e.full_name }))}
            />
            <Select
              id="nb-client"
              error={fieldErrors.client}
              label="Learner"
              required
              placeholder="Choose a learner"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              options={clients.map((c) => ({
                value: String(c.id),
                label: c.child_name
                  ? `${c.guardian_first_name} ${c.guardian_surname} (${c.child_name})`
                  : `${c.guardian_first_name} ${c.guardian_surname}`,
              }))}
            />
            <Select
              id="nb-session-type"
              error={fieldErrors.sessionType}
              label="Session type"
              required
              placeholder="Choose a session type"
              hint="From the L360 price list — what this session is billed as"
              value={sessionTypeId}
              onChange={(e) => setSessionTypeId(e.target.value)}
              options={sessionTypes.map((st) => ({ value: String(st.id), label: st.name }))}
            />
            <Input
              id="nb-time"
              label="Start time"
              type="time"
              required
              value={time}
              onChange={(e) => setTime(e.target.value)}
            />
            <Select
              id="nb-duration"
              label="Duration"
              required
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              options={DURATION_OPTIONS}
            />
            <Select
              id="nb-repeat"
              label="Repeat"
              required
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
              options={REPEAT_OPTIONS}
            />
            {repeat !== "none" && (
              <Input
                id="nb-repeat-ends"
                error={fieldErrors.repeatEndsOn}
                label="Repeat until"
                type="date"
                required
                min={date}
                value={repeatEndsOn}
                onChange={(e) => setRepeatEndsOn(e.target.value)}
              />
            )}
            <Textarea
              id="nb-notes"
              label="Notes"
              hint="Optional"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />

            <div style={{ display: "flex", gap: 8 }}>
              <Button type="submit" loading={submitting} loadingLabel="Booking…">
                Book session
              </Button>
              <Button type="button" variant="secondary" onClick={onClose}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
    </Modal>
  );
}

// --- Booking detail modal ---------------------------------------------------

interface BookingDetailModalProps {
  booking: Booking;
  me: Me | null;
  onClose: () => void;
  onChanged: () => void;
}

function BookingDetailModal({ booking, me, onClose, onChanged }: BookingDetailModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [moveDate, setMoveDate] = useState(toDateInputValue(new Date(booking.start_utc)));
  const [moveTime, setMoveTime] = useState(toTimeInputValue(booking.start_utc));
  // Live pill preview while the Confirm flow is mid-decision.
  const [preview, setPreview] = useState<OutcomePreview>(null);
  const { variant, label } = statusBadgeProps(preview ? { ...booking, ...preview } : booking);
  const billing = billingBadgeProps(
    preview ? (preview.charge_waived ? "fee_waived" : "to_bill") : booking.billing_state,
  );
  const isPast = new Date(booking.start_utc).getTime() <= Date.now();
  const isAdminUser = me?.role === "admin";
  const canConfirm =
    isPast &&
    !booking.invoiced &&
    // A waived fee is final for educators; admins may revisit it
    // (Simon, 03/09/2026).
    (!booking.charge_waived || isAdminUser) &&
    (booking.status === "confirmed" || booking.status === "completed" || booking.status === "no_show" || booking.status === "cancelled_late") &&
    !!me &&
    (isAdminUser || booking.educator_id === me.id);
  // On an invoice = locked: no move, no cancel (the server refuses too).
  const canModify = booking.status === "confirmed" && !booking.invoiced;
  // Inside 24h the cancellation is "late" and the canceller decides whether
  // the family is charged — same question the Bookings list asks.
  const isLateCancel = new Date(booking.start_utc).getTime() - Date.now() < 24 * 3_600_000;

  async function handleCancel(charge?: boolean) {
    setError(null);
    setBusy(true);
    try {
      await cancelBooking(booking.id, charge);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't cancel this booking.");
    } finally {
      setBusy(false);
    }
  }

  async function handleMove() {
    setError(null);
    setBusy(true);
    try {
      await moveBooking(booking.id, { start_utc: combineDateTime(moveDate, moveTime) });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't move this booking.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal onClose={onClose}>
        <Card eyebrow={booking.room_name} title={booking.educator_name}>
          <p style={{ marginBottom: 8 }}>{booking.client_label}</p>
          {booking.service_type_name && (
            <p style={{ marginBottom: 8 }}>
              {booking.service_type_name}
              {booking.client_price_cents !== null && (
                <>
                  {" — "}
                  <Money cents={booking.client_price_cents} />
                </>
              )}
            </p>
          )}
          <p style={{ marginBottom: 8, display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <StatusBadge variant={variant} label={preview ? `${label} …` : label} />
            {billing && <StatusBadge variant={billing.variant} label={billing.label} />}
            <span className="l360-mono">
              {toTimeInputValue(booking.start_utc)} · {booking.duration_minutes} min
            </span>
          </p>
          {canConfirm && (
            <div style={{ marginBottom: 16 }}>
              <ConfirmSessionFlow
                booking={booking}
                onPreview={setPreview}
                onDone={onChanged}
                onError={setError}
              />
            </div>
          )}
          {booking.notes && <p style={{ marginBottom: 16, color: "var(--l360-bgrey)" }}>{booking.notes}</p>}
          {booking.charge_waived && booking.outcome_reason && (
            <p className="l360-field-hint" style={{ marginBottom: 16 }}>Fee waived — {booking.outcome_reason}</p>
          )}
          {booking.invoiced && (
            <p className="l360-field-hint" style={{ marginBottom: 16 }}>
              This session is on an invoice — it can no longer be moved, cancelled or amended.
            </p>
          )}
          {booking.invoiced && isAdminUser && booking.invoice_id && (
            <div style={{ marginBottom: 16 }}>
              <VoidInvoiceModal
                booking={booking}
                voidAction={(invId) => voidInvoice(invId)}
                onDone={onChanged}
                onError={setError}
              />
            </div>
          )}

          {error && (
            <div className="l360-alert l360-alert-danger" role="alert">
              ⚠ {error}
            </div>
          )}

          {canModify && (
            <>
              <div className="l360-field" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Input
                  id="move-date"
                  label="Move to date"
                  type="date"
                  value={moveDate}
                  onChange={(e) => setMoveDate(e.target.value)}
                />
                <Input
                  id="move-time"
                  label="Move to time"
                  type="time"
                  value={moveTime}
                  onChange={(e) => setMoveTime(e.target.value)}
                />
              </div>
              <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
                <Button type="button" variant="secondary" onClick={handleMove} loading={busy} loadingLabel="Moving…">
                  Move booking
                </Button>

                {!isLateCancel && !confirmingCancel && (
                  <Button type="button" variant="destructive" onClick={() => setConfirmingCancel(true)}>
                    Cancel booking
                  </Button>
                )}
                {isLateCancel && (
                  <LateCancelModal
                    booking={booking}
                    cancelAction={(charge, reason) => cancelBooking(booking.id, charge, reason)}
                    onDone={onChanged}
                    onError={setError}
                  />
                )}
              </div>

              {confirmingCancel && !isLateCancel && (
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
                  <span>Cancel this booking?</span>
                  <Button type="button" variant="destructive" onClick={() => handleCancel()} loading={busy} loadingLabel="Cancelling…">
                    Yes, cancel
                  </Button>
                  <Button type="button" variant="secondary" onClick={() => setConfirmingCancel(false)}>
                    No
                  </Button>
                </div>
              )}


            </>
          )}

          <Button type="button" variant="secondary" onClick={onClose}>
            Close
          </Button>
        </Card>
    </Modal>
  );
}
