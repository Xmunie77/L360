import { describe, expect, it } from "vitest";
import { layoutLanes } from "./lanes";

describe("layoutLanes", () => {
  it("gives a lone item the full width", () => {
    expect(layoutLanes([{ start: 9, end: 10 }])).toEqual([{ lane: 0, laneCount: 1 }]);
  });

  it("keeps back-to-back sessions full width", () => {
    // 09:00-10:00 then 10:00-11:00 don't overlap — neither should shrink.
    expect(layoutLanes([{ start: 9, end: 10 }, { start: 10, end: 11 }])).toEqual([
      { lane: 0, laneCount: 1 },
      { lane: 0, laneCount: 1 },
    ]);
  });

  it("splits two overlapping sessions into halves", () => {
    expect(layoutLanes([{ start: 9, end: 10.5 }, { start: 10, end: 11 }])).toEqual([
      { lane: 0, laneCount: 2 },
      { lane: 1, laneCount: 2 },
    ]);
  });

  it("handles a session fully nested inside another", () => {
    expect(layoutLanes([{ start: 9, end: 12 }, { start: 10, end: 11 }])).toEqual([
      { lane: 0, laneCount: 2 },
      { lane: 1, laneCount: 2 },
    ]);
  });

  it("reuses a lane once its previous session has finished", () => {
    // A 9-12 spans both; 9-10 and 10-11 stack in the second lane.
    expect(
      layoutLanes([{ start: 9, end: 12 }, { start: 9, end: 10 }, { start: 10, end: 11 }]),
    ).toEqual([
      { lane: 0, laneCount: 2 },
      { lane: 1, laneCount: 2 },
      { lane: 1, laneCount: 2 },
    ]);
  });

  it("does not let one busy cluster shrink an unrelated later session", () => {
    const out = layoutLanes([
      { start: 9, end: 10 },
      { start: 9, end: 10 },
      { start: 14, end: 15 },
    ]);
    expect(out[0].laneCount).toBe(2);
    expect(out[2]).toEqual({ lane: 0, laneCount: 1 });
  });

  it("returns lanes in the input order, not sorted order", () => {
    const out = layoutLanes([{ start: 11, end: 12 }, { start: 9, end: 10 }]);
    expect(out).toEqual([{ lane: 0, laneCount: 1 }, { lane: 0, laneCount: 1 }]);
  });

  it("returns an empty array for no items", () => {
    expect(layoutLanes([])).toEqual([]);
  });
});
