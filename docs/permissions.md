# Permissions

Sentinel is designed to run as a normal user with no persistent elevated privileges. This document lists every permission the tool uses, why it needs it, and what happens without it.

---

## macOS permissions

### Process list access

| Property | Detail |
|---|---|
| **Why needed** | Core process monitoring — lists all running programs |
| **Feature enabled** | `sentinel processes`, Apps tab, process attribution in scan |
| **Without it** | Sentinel cannot run at all |
| **How to revoke** | Not applicable — this is a standard user privilege |

Sentinel reads the process list via `psutil`, which uses standard macOS APIs. It can see all processes owned by the current user. Processes owned by other users or protected by System Integrity Protection (SIP) may return `AccessDenied` and are skipped gracefully.

---

### Network connections access

| Property | Detail |
|---|---|
| **Why needed** | Port monitoring and connection attribution |
| **Feature enabled** | `sentinel ports`, `sentinel network`, Network tab, exposure classification |
| **Without it** | Port and connection tables will be empty or partial |
| **How to revoke** | Not applicable — requires no grant; access depends on macOS SIP |

On macOS, reading the full network connection table with process attribution requires either elevated privileges or the process to own the connection. `sentinel doctor` will tell you if this permission is unavailable in your environment.

To get full visibility:
```bash
sudo sentinel scan
```

---

### File system read access (executables)

| Property | Detail |
|---|---|
| **Why needed** | Computing file hashes and checking executable existence |
| **Feature enabled** | Executable existence check, deep scan hashing (Phase 7) |
| **Without it** | Hashes cannot be computed for protected paths; existence check may fail silently |
| **How to revoke** | macOS Full Disk Access in System Preferences → Privacy & Security |

Sentinel only reads executables that are already listed as the path of a running process. It does not scan arbitrary files.

---

### macOS Full Disk Access (optional, Phase 7)

| Property | Detail |
|---|---|
| **Why needed** | Computing hashes for executables in protected locations (system directories) |
| **Feature enabled** | Complete deep scan coverage |
| **Without it** | Deep scan skips protected paths; coverage is partial but noted in output |
| **How to grant** | System Preferences → Privacy & Security → Full Disk Access → add `sentinel` |
| **How to revoke** | Remove `sentinel` from the Full Disk Access list |

---

## Browser extension permissions (Phase 8)

The browser extension will request the following permissions:

| Permission | Why needed | What happens without it |
|---|---|---|
| `tabs` | Know which site is active | Site context unavailable |
| `webRequest` | Observe outbound requests | Third-party request detection unavailable |
| `cookies` | Observe cookie metadata (not values) | Cookie tracking unavailable |
| `nativeMessaging` | Send events to the local Sentinel agent | Extension cannot communicate with Sentinel |

The extension will **not** request:
- `history` — browsing history is not relevant to Sentinel's goals
- `bookmarks` — not relevant
- `clipboardRead` / `clipboardWrite` — not relevant
- `<all_urls>` with full URL access — host/domain is sufficient

---

## No persistent elevated access

Sentinel does not:
- Install a privileged helper tool
- Register a launch daemon running as root
- Modify `/etc/hosts` or any system file
- Add itself to sudoers

If a future phase requires elevated access for a specific feature, it will be gated behind an explicit user grant (e.g. macOS SMJobBless for a privileged helper), documented here, and removable without reinstalling the whole application.

---

## Revoking all access

To completely remove Sentinel and all permissions:

```bash
# Remove the application
pipx uninstall macsentry       # or: poetry env remove python

# Remove stored data
rm -rf ~/.local/share/macsentry/

# Remove browser extension
# Open browser extensions page and remove "Sentinel Privacy Monitor"
```

No other system locations are modified.
