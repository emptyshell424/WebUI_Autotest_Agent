# Experiment Scenarios

Use these scenarios to build a small but reproducible graduation-project evaluation set.

## First-pass generation scenarios

1. Open a login page, enter credentials, submit, and verify the dashboard welcome text.
2. Open a search engine, search a keyword, and verify the results container appears.
3. Open a registration form, fill required fields, submit, and verify a success message.
4. Open a list page, search by keyword, and verify the filtered result row appears.
5. Open a detail page, click a tab, and verify the tab content becomes visible.

## Complex interaction scenarios

6. Interact with a page that loads content asynchronously and verify the delayed card list.
7. Operate inside a dialog and verify a confirmation banner after submission.
8. Switch into an iframe, submit a form, and verify a success message.
9. Open a page that launches a new window and verify the destination page title.
10. Handle an alert or confirmation dialog and verify the resulting state change.

## Self-heal scenarios

11. Change a button selector so the initial script fails, then verify the repaired script succeeds.
12. Change an input selector from `id` to `name` and verify the self-heal flow repairs it.
13. Insert a loading delay so the initial wait is insufficient, then verify the repaired script succeeds.
14. Wrap the target element inside an iframe and verify the repaired script switches context.
15. Trigger a dialog-based interaction and verify the repaired script targets the dialog container.
