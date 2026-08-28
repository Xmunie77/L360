import { useEffect, useMemo, useState, type CSSProperties, type FormEvent, type MouseEvent } from "react";
import { Button, Card, Input, Select, StatusBadge, Textarea } from "../ui/ui";
import {
  ApiError,
  cancelBooking,
  createBooking,
  createBookingSeries,
  listBookings,
  listClients,
  listEducators,
  listRooms,
  moveBooking,
  type Booking,
  type Client,
  type Duration,
  type Educator,
  type Me,
  type Room,
  type SkippedOccurrence,
} from "../api/client";
import { statusBadgeProps } from "../domain/status";
import {
  combineDateTime,
  dayBoundsISO,
  formatHourLabel,
  localHourFraction,
  mondayBasedWeekday,
  todayStr,
  toTimeInputValue,
} from "../domain/datetime";

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
}

// Day view: one column per active room, a time axis down the left, sessions
// rendered as positioned blocks. Click an empty column to book, click a
// block to see/cancel/move it. Plain CSS grid + absolute positioning — no
// calendar library.
export function Calendar({ me }: { me: Me | null }) {
  const [date, setDate] = useState<string>(todayStr());
  const [rooms, setRooms] = useState<Room[]>([]);
  const [educators, setEducators] = useState<Educator[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [newBookingDraft, setNewBookingDraft] = useState<NewBookingDraft | null>(null);
  const [selectedBooking, setSelectedBooking] = useState<Booking | null>(null);

  // Reference data — fetched once.
  useEffect(() => {
    Promise.all([listRooms(), listEducators(), listClients()])
      .then(([r, e, c]) => {
        setRooms(r);
        setEducators(e);
        setClients(c);
      })
      .catch((err) => {
        setLoadError(err instanceof ApiError ? err.detail : "Couldn't load rooms, educators or clients.");
      });
  }, []);

  async function refreshBookings() {
    setLoading(true);
    setLoadError(null);
    try {
      const { startISO, endISO } = dayBoundsISO(date);
      const rows = await listBookings({ start: startISO, end: endISO });
      setBookings(rows);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.detail : "Couldn't load bookings for this day.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshBookings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  const activeRooms = useMemo(() => rooms.filter((r) => r.active), [rooms]);

  const { startHour, endHour } = useMemo(() => {
    let start = DEFAULT_START_HOUR;
    let end = DEFAULT_END_HOUR;
    for (const b of bookings) {
      const s = localHourFraction(b.start_utc);
      const e = s + b.duration_minutes / 60;
      if (s < start) start = Math.floor(s);
      if (e > end) end = Math.ceil(e);
    }
    return { startHour: start, endHour: end };
  }, [bookings]);

  const totalHours = endHour - startHour;
  const gridHeight = totalHours * HOUR_PX;
  const hourMarks = useMemo(() => {
    const marks: number[] = [];
    for (let h = startHour; h <= endHour; h++) marks.push(h);
    return marks;
  }, [startHour, endHour]);

  function bookingsForRoom(roomId: number): Booking[] {
    return bookings.filter((b) => b.room_id === roomId);
  }

  function handleColumnClick(e: MouseEvent<HTMLDivElement>, roomId: number) {
    const rect = e.currentTarget.getBoundingClientRect();
    const offsetY = e.clientY - rect.top;
    let hour = startHour + offsetY / HOUR_PX;
    // Snap to the nearest 15 minutes and keep it inside the visible range.
    hour = Math.round(hour * 4) / 4;
    hour = Math.min(Math.max(hour, startHour), endHour - 0.25);
    setNewBookingDraft({ roomId, time: formatHourLabel(hour) });
  }

  return (
    <>
      <Card eyebrow="Scheduling" title="Calendar">
        <div className="l360-cal-toolbar">
          <Input
            id="cal-date"
            label="Day"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <Button type="button" variant="secondary" onClick={() => setDate(todayStr())}>
            Today
          </Button>
        </div>

        {loadError && (
          <div className="l360-alert l360-alert-danger" role="alert">
            ⚠ {loadError}
          </div>
        )}

        {!loadError && activeRooms.length === 0 && !loading && (
          <p className="l360-empty">No active rooms configured yet.</p>
        )}

        {activeRooms.length > 0 && (
          <div className="l360-cal-grid-wrap">
            <div
              className="l360-cal-grid"
              style={{ gridTemplateColumns: `72px repeat(${activeRooms.length}, minmax(160px, 1fr))` }}
            >
              <div className="l360-cal-corner" aria-hidden="true" />
              {activeRooms.map((room) => (
                <div key={room.id} className="l360-cal-room-head">{room.name}</div>
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

              {activeRooms.map((room) => (
                <div
                  key={room.id}
                  className="l360-cal-room-col"
                  style={{ height: gridHeight, "--l360-cal-hour-h": `${HOUR_PX}px` } as CSSProperties}
                  onClick={(e) => handleColumnClick(e, room.id)}
                  role="button"
                  tabIndex={0}
                  aria-label={`New booking in ${room.name}`}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setNewBookingDraft({ roomId: room.id, time: formatHourLabel(startHour) });
                    }
                  }}
                >
                  {bookingsForRoom(room.id).map((b) => {
                    const top = (localHourFraction(b.start_utc) - startHour) * HOUR_PX;
                    const height = Math.max((b.duration_minutes / 60) * HOUR_PX, 24);
                    const { variant, label } = statusBadgeProps(b.status);
                    return (
                      <button
                        key={b.id}
                        type="button"
                        className={`l360-cal-block l360-cal-block-${b.status}`}
                        style={{ top, height }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedBooking(b);
                        }}
                      >
                        <span className="l360-cal-block-title">{b.educator_name}</span>
                        <span className="l360-cal-block-sub">{b.client_label}</span>
                        <span className="l360-cal-block-sub">{variant === "success" ? "" : label}</span>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {newBookingDraft && (
        <NewBookingModal
          draft={newBookingDraft}
          date={date}
          rooms={activeRooms}
          educators={educators}
          clients={clients}
          me={me}
          onClose={() => setNewBookingDraft(null)}
          onCreated={() => {
            setNewBookingDraft(null);
            refreshBookings();
          }}
        />
      )}

      {selectedBooking && (
        <BookingDetailModal
          booking={selectedBooking}
          date={date}
          onClose={() => setSelectedBooking(null)}
          onChanged={() => {
            setSelectedBooking(null);
            refreshBookings();
          }}
        />
      )}
    </>
  );
}

// --- New booking modal -----------------------------------------------------

interface NewBookingModalProps {
  draft: NewBookingDraft;
  date: string;
  rooms: Room[];
  educators: Educator[];
  clients: Client[];
  me: Me | null;
  onClose: () => void;
  onCreated: () => void;
}

function NewBookingModal({ draft, date, rooms, educators, clients, me, onClose, onCreated }: NewBookingModalProps) {
  const [roomId, setRoomId] = useState(String(draft.roomId));
  // If the person booking is themselves a bookable educator, default the
  // field to them — they're usually booking their own session — but leave
  // it editable (an admin/educator can still book on someone else's behalf).
  const [educatorId, setEducatorId] = useState(
    me && educators.some((e) => e.id === me.id) ? String(me.id) : "",
  );
  const [clientId, setClientId] = useState("");
  const [time, setTime] = useState(draft.time);
  const [duration, setDuration] = useState("60");
  const [notes, setNotes] = useState("");
  const [repeat, setRepeat] = useState("none");
  const [repeatEndsOn, setRepeatEndsOn] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [skipped, setSkipped] = useState<SkippedOccurrence[] | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!educatorId || !clientId) {
      setError("Choose an educator and a client.");
      return;
    }
    if (repeat !== "none" && !repeatEndsOn) {
      setError("Choose a date to repeat until.");
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
      <div className="l360-modal-backdrop" onClick={onClose}>
        <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
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
        </div>
      </div>
    );
  }

  return (
    <div className="l360-modal-backdrop" onClick={onClose}>
      <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
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
              label="Educator"
              required
              placeholder="Choose an educator"
              value={educatorId}
              onChange={(e) => setEducatorId(e.target.value)}
              options={educators.map((e) => ({ value: String(e.id), label: e.full_name }))}
            />
            <Select
              id="nb-client"
              label="Client"
              required
              placeholder="Choose a client"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              options={clients.map((c) => ({
                value: String(c.id),
                label: c.child_name
                  ? `${c.guardian_first_name} ${c.guardian_surname} (${c.child_name})`
                  : `${c.guardian_first_name} ${c.guardian_surname}`,
              }))}
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
      </div>
    </div>
  );
}

// --- Booking detail modal ---------------------------------------------------

interface BookingDetailModalProps {
  booking: Booking;
  date: string;
  onClose: () => void;
  onChanged: () => void;
}

function BookingDetailModal({ booking, date, onClose, onChanged }: BookingDetailModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [moveTime, setMoveTime] = useState(toTimeInputValue(booking.start_utc));
  const { variant, label } = statusBadgeProps(booking.status);
  const canModify = booking.status === "confirmed";

  async function handleCancel() {
    setError(null);
    setBusy(true);
    try {
      await cancelBooking(booking.id);
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
      await moveBooking(booking.id, { start_utc: combineDateTime(date, moveTime) });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't move this booking.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="l360-modal-backdrop" onClick={onClose}>
      <div className="l360-modal-card" onClick={(e) => e.stopPropagation()}>
        <Card eyebrow={booking.room_name} title={booking.educator_name}>
          <p style={{ marginBottom: 8 }}>{booking.client_label}</p>
          <p style={{ marginBottom: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <StatusBadge variant={variant} label={label} />
            <span className="l360-mono">
              {toTimeInputValue(booking.start_utc)} · {booking.duration_minutes} min
            </span>
          </p>
          {booking.notes && <p style={{ marginBottom: 16, color: "var(--l360-bgrey)" }}>{booking.notes}</p>}

          {error && (
            <div className="l360-alert l360-alert-danger" role="alert">
              ⚠ {error}
            </div>
          )}

          {canModify && (
            <>
              <div className="l360-field">
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

                {!confirmingCancel && (
                  <Button type="button" variant="destructive" onClick={() => setConfirmingCancel(true)}>
                    Cancel booking
                  </Button>
                )}
              </div>

              {confirmingCancel && (
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
                  <span>Cancel this booking?</span>
                  <Button type="button" variant="destructive" onClick={handleCancel} loading={busy} loadingLabel="Cancelling…">
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
      </div>
    </div>
  );
}
