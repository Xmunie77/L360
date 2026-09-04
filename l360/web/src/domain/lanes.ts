// Side-by-side placement for overlapping calendar blocks.
//
// Until 04/09/2026 two sessions at the same time in the same column rendered
// on top of each other, hiding one entirely. This splits a column's items
// into lanes: everything that overlaps in time shares a cluster, and each
// item takes the first lane free within it. `laneCount` is the cluster's
// width, so a pair of overlapping sessions each take half the column while
// an unclashing one still takes the whole width.

export interface Span {
  /** Start, in any consistent unit (we use local hour fractions). */
  start: number;
  /** End, same unit. Must be >= start. */
  end: number;
}

export interface Lane {
  lane: number;
  laneCount: number;
}

/** Lane placement per input item, returned in the SAME order as `items`. */
export function layoutLanes<T extends Span>(items: T[]): Lane[] {
  // Earliest first; on a tie the LONGER session takes the left lane, so a
  // two-hour block reads as the spine with shorter ones stacked beside it.
  const order = items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => a.item.start - b.item.start || b.item.end - a.item.end);

  const result: Lane[] = new Array(items.length);
  // A cluster is a run of items connected by overlap — its members share a
  // lane count, so we can only assign widths once the run has closed.
  let cluster: { index: number; lane: number }[] = [];
  let clusterEnd = -Infinity;
  let laneEnds: number[] = [];

  function closeCluster() {
    const laneCount = Math.max(laneEnds.length, 1);
    for (const member of cluster) {
      result[member.index] = { lane: member.lane, laneCount };
    }
    cluster = [];
    laneEnds = [];
    clusterEnd = -Infinity;
  }

  for (const { item, index } of order) {
    if (item.start >= clusterEnd) closeCluster();
    // First lane whose last item has already finished; otherwise a new one.
    let lane = laneEnds.findIndex((end) => end <= item.start);
    if (lane === -1) {
      lane = laneEnds.length;
      laneEnds.push(item.end);
    } else {
      laneEnds[lane] = item.end;
    }
    cluster.push({ index, lane });
    clusterEnd = Math.max(clusterEnd, item.end);
  }
  closeCluster();

  return result;
}
