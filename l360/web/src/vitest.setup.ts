// Global Vitest setup — without this, React Testing Library doesn't auto-run
// its unmount/cleanup between tests (that auto-registration only fires when
// vitest's `globals: true` exposes `afterEach` on the global object, which
// this project's config deliberately doesn't set), so DOM from one test's
// render() leaks into the next and duplicate-text queries start failing.
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
