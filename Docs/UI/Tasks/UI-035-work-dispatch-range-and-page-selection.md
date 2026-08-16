# UI-035 — Work Dispatch Range and Current-Page Selection

## Task ID

`UI-035` — Status: `Complete`

## Goal

Make large Album selection on the AI Work Dispatch Available page faster and
more familiar without selecting hidden pages or ineligible Albums.

## Interaction Contract

1. Clicking an eligible Album checkbox establishes the range-selection anchor.
2. Shift-clicking another checkbox applies its checked state to the inclusive
   range between the anchor and the clicked Album.
3. Ineligible Albums in a range remain unselected and disabled.
4. The table-header checkbox selects or clears every eligible Album on the
   current loaded page only.
5. The header checkbox displays checked, unchecked, or indeterminate state that
   reflects the current page selection.
6. Filter, page, page-size, Worker, and view changes reset selection and its
   range anchor, preserving the existing current-page safety boundary.
7. The existing Select current page action remains available and uses the same
   selection behavior.

## Acceptance Criteria

- Shift-click selects and deselects an inclusive eligible range.
- Current-page select-all excludes disabled Albums.
- Clearing the header checkbox clears the current selection.
- Partial selection sets the header checkbox to indeterminate.
- Preview count and enabled state remain synchronized.
