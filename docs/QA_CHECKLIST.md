# AI DeskMate — Manual Clean-Machine QA Checklist

This checklist is designed for end-to-end quality assurance on a clean Windows 10/11 machine or virtual machine (VM) with **no pre-existing Python environment or development tools installed**.

---

## 📋 Phase 1: Installation & First Launch

| Step | Action | Expected Result | Pass / Fail |
| :---: | :--- | :--- | :---: |
| **1.1** | Copy `dist\AI-DeskMate-Setup-1.0.0.exe` to clean machine. Run installer. | Installer wizard launches with AI DeskMate branding and license agreement. | [ ] |
| **1.2** | Select destination folder (default: `%ProgramFiles%\AI DeskMate` or user local). | Installation proceeds cleanly without requiring admin privileges if run as user. | [ ] |
| **1.3** | Check **"Start AI DeskMate when I sign in"** checkbox. Complete setup. | Installer exits cleanly and creates Start Menu and optional Desktop shortcuts. | [ ] |
| **1.4** | Launch AI DeskMate from Start Menu. | The **Onboarding Wizard** displays automatically on first run. | [ ] |
| **1.5** | Choose an avatar (e.g. Mochi the Cat), enter a name, choose a tone (e.g. Chill). Click "Begin Journey". | Onboarding closes. Floating avatar overlay appears in bottom-right corner. System tray icon appears. | [ ] |

---

## 📋 Phase 2: Live Activity & Wellness Interventions

| Step | Action | Expected Result | Pass / Fail |
| :---: | :--- | :--- | :---: |
| **2.1** | Open Notepad or a browser and type continuously for 2–3 minutes. | Background tracker records keystroke counts in `%APPDATA%\AI DeskMate\deskmate.db`. | [ ] |
| **2.2** | Inspect System Tray menu. Click **"🏥 System Health"**. | Message box displays status: Tracker Running, DB size > 0 KB, Model status, Last Heartbeat. | [ ] |
| **2.3** | Right-click tray and select **"💧 Water Reminder Test"** or wait for an interval nudge. | Avatar transitions to `alert` state. Speech bubble displays reminder in selected personality tone. | [ ] |
| **2.4** | Click **"Done! 👍"** or **"Snooze 💤"** in the avatar popup. | Avatar plays celebrate animation on "Done", closes speech bubble, and logs response in `nudge_log`. | [ ] |
| **2.5** | Test offline TTS: Enable TTS in Settings and trigger test nudge. | System voice speaks the reminder aloud cleanly without errors. | [ ] |

---

## 📋 Phase 3: Analytics Dashboard & Insights

| Step | Action | Expected Result | Pass / Fail |
| :---: | :--- | :--- | :---: |
| **3.1** | Right-click tray icon and select **"📊 Open Dashboard"**. | Default browser automatically opens to `http://127.0.0.1:<port>` on an ephemeral port. | [ ] |
| **3.2** | Check dashboard header. | Header displays user's companion avatar icon, avatar name, and user name. | [ ] |
| **3.3** | Verify KPI metric cards and charts. | Daily screentime, break adherence, and energy ratings render properly with Plotly. | [ ] |
| **3.4** | Check Top Insights section. | Displays friendly guidance cards or computed insights based on available sample size. | [ ] |
| **3.5** | Close browser tab. Confirm main companion continues running quietly in system tray. | Companion remains responsive; no orphan processes or high CPU spikes. | [ ] |

---

## 📋 Phase 4: Demo Mode Verification

| Step | Action | Expected Result | Pass / Fail |
| :---: | :--- | :--- | :---: |
| **4.1** | Launch application with `--demo` flag: `AIDeskMate.exe --demo`. | Application boots in Demo mode using isolated `demo.db` in `%APPDATA%\AI DeskMate`. | [ ] |
| **4.2** | Check System Tray menu header. | Shows `🧪 [Demo] AI DeskMate (Mochi)` and contains `🎭 Trigger Sample Nudge`. | [ ] |
| **4.3** | Click `🎭 Trigger Sample Nudge` repeatedly. | Avatar cycles through Water, Posture, Eye Rest, Break, and Fatigue Predicted nudges across tones. | [ ] |
| **4.4** | Open dashboard from Demo mode. | Dashboard displays prominent badge: `🧪 Demo Mode (Synthetic Data)`. Shows 4 weeks of charts. | [ ] |
| **4.5** | Confirm real database isolation. | Real `deskmate.db` remains completely untouched. | [ ] |

---

## 📋 Phase 5: Resilience & Operating System Edge Cases

| Step | Action | Expected Result | Pass / Fail |
| :---: | :--- | :--- | :---: |
| **5.1** | Sleep / Suspend: Put laptop to sleep for 5 minutes, then wake up. | Streak counters reset; 3-minute post-wake grace period suppresses alerts; no fake gap logs. | [ ] |
| **5.2** | Focus Theft Test: Click active window (e.g. typing game or text editor) while avatar alerts. | Avatar overlay does **not** steal active keyboard focus (`WS_EX_NOACTIVATE`). | [ ] |
| **5.3** | Unclean Shutdown: Kill `AIDeskMate.exe` via Task Manager. Relaunch app. | Startup detects unclean heartbeat, flushes partial minute, logs recovery event, and resumes cleanly. | [ ] |
| **5.4** | Single-Instance Guard: Attempt to launch `AIDeskMate.exe` a second time while already running. | Second instance detects active lockfile with running PID and exits immediately. | [ ] |

---

## 📋 Phase 6: Uninstallation & Data Retention

| Step | Action | Expected Result | Pass / Fail |
| :---: | :--- | :--- | :---: |
| **6.1** | Open Windows Settings > Apps > Installed apps. Select "AI DeskMate" > Uninstall. | Uninstaller launches and removes executable binaries and registry entries. | [ ] |
| **6.2** | When prompted: *"Would you like to keep your collected activity history...?"*, click **"Yes"**. | Files in `%ProgramFiles%` are deleted; `%APPDATA%\AI DeskMate` is preserved. | [ ] |
| **6.3** | Reinstall AI DeskMate. Launch. | Previously configured avatar, settings, and activity history are loaded seamlessly. | [ ] |
| **6.4** | Uninstall again. When prompted, click **"No"**. | `%APPDATA%\AI DeskMate` is completely deleted. Zero leftover files on system. | [ ] |
