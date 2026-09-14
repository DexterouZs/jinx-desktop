// Called only after Jinx opens a user-requested page in the default Firefox.
for (const window of workspace.windowList()) {
    if (String(window.resourceClass).toLowerCase().includes('firefox')) {
        window.minimized = false;
        workspace.activeWindow = window;
        break;
    }
}
