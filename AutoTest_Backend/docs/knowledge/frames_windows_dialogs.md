# Frames, Windows, and Dialogs

1. If a target element lives inside an `iframe`, switch to the frame before locating the element and switch back after the interaction.
2. When a click opens a new window or tab, wait for the window handles count to change before switching.
3. For browser alerts, use `WebDriverWait` with `alert_is_present()` before accepting or dismissing the alert.
4. Modal dialogs are often easier to automate by waiting for the dialog container, then locating controls inside that container.
5. When a script fails after a popup or window transition, verify that the active context is still correct.
