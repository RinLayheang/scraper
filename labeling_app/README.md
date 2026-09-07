# 🛡️ KCMS Collaborative Khmer Comment Labeler

A high-performance, real-time collaborative web application designed for annotating and moderating Khmer social media comments. Built with **FastAPI**, **Vanilla Modern CSS**, and **Vanilla JavaScript**, featuring zero page bloat, instant multi-user concurrency control, and native-feeling mobile touch ergonomics.

---

## 📋 Table of Contents
- [✨ Key Features](#-key-features)
- [🚀 How to Run](#-how-to-run)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Quick Start Scripts](#2-quick-start-scripts)
  - [3. Remote Sharing via Cloudflare Tunnel](#3-remote-sharing-via-cloudflare-tunnel)
- [📖 How to Use the Labeler](#-how-to-use-the-labeler)
  - [Annotation Schema](#annotation-schema)
  - [Keyboard Shortcuts (Desktop)](#keyboard-shortcuts-desktop)
  - [Mobile Usage & Ergonomics](#mobile-usage--ergonomics)
  - [Editing Previous Labels (History)](#editing-previous-labels-history)
  - [Leaderboard & Exporting](#leaderboard--exporting)
- [⚙️ Technical Architecture](#️-technical-architecture)
- [📁 Directory Structure](#-directory-structure)

---

## ✨ Key Features

- 👥 **Multi-User Collaboration**: Users annotate simultaneously without conflicts. Each user receives a unique unlabelled comment.
- ⏱️ **Active Lease & Fail-Safe Locking**: Comments are leased for 60 seconds with heartbeat renewal. Leaving or closing a tab immediately releases the lease via `navigator.sendBeacon`.
- ✏️ **Historical Label Editing**: Review recent annotations in the History modal and edit ratings directly without touching raw CSV files.
- 📱 **Zero-Scroll Mobile Layout**: 2-column side-by-side axes, 5-line scrollable Khmer text box with Kantumruy Pro font, and tactile 32px touch buttons.
- ⌨️ **Lightning-Fast Desktop Hotkeys**: Complete annotations using number keys `[1, 2, 3]`, letters `[Q, W, E]`, and `[Enter]`.
- 🎵 **On-Demand Background Music**: Relaxing audio player that lazy-loads only when tapped (zero network bandwidth on initial load).
- 🏆 **Live Team Leaderboard & Stats**: Tracks team progress, individual contributor rankings, and class distributions.
- 💾 **Dual CSV Atomic Synchronization**: Automatically updates both `scraper/raw_data/cleaned_comments.csv` and `ai_engine/data/comments.csv`.

---

## 🚀 How to Run

### 1. Prerequisites

Ensure **Python 3.8+** is installed on your computer. Install the required Python dependencies:

```bash
pip install fastapi uvicorn pandas pydantic
```

---

### 2. Quick Start Scripts

#### **On macOS / Linux**:
1. Open your terminal and navigate to the directory:
   ```bash
   cd scraper/labeling_app
   ```
2. Make the script executable (first time only):
   ```bash
   chmod +x run_server.sh run.py
   ```
3. Run the launcher:
   ```bash
   ./run_server.sh
   ```

#### **On Windows**:
1. Navigate to `scraper\labeling_app\`.
2. Double-click **`run_server.bat`** (or open Command Prompt / PowerShell and run `run_server.bat`).

#### **Alternative (Direct Python Command)**:
```bash
cd scraper/labeling_app
python run.py
```
Or directly with Uvicorn:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Once started, open your web browser at:
```
http://localhost:8000
```
Or on your local Wi-Fi network:
```
http://<YOUR_LOCAL_IP>:8000
```

---

### 3. Remote Sharing via Cloudflare Tunnel

Want your friends or teammates to help label from their phones or homes?
The launcher **automatically creates a secure HTTPS public link** using Cloudflare Tunnel:

- **If `cloudflared` is installed** (`brew install cloudflared` on Mac, or Windows release):
  The launcher starts a tunnel automatically and prints:
  ```
  ⚡ Cloudflare detected! Launching secure public tunnel...
  🌐 Multi-User Public HTTPS URL:
     https://your-unique-tunnel.trycloudflare.com
  ```
- **If Node.js is installed**: It will automatically launch via `npx -y cloudflared`.
- Share this HTTPS URL with your teammates—anyone on mobile or desktop can access it without port forwarding or VPNs!

---

## 📖 How to Use the Labeler

### 1. Joining a Session
1. When you first open the web app, a prompt will ask for your **Name** (e.g. `Oudom`).
2. Your name is stored in your browser's local storage and used to track leaderboard contributions. You can change your name anytime by clicking your user pill in the top header.

---

### 2. Annotation Schema

Every comment must be evaluated along **two independent axes**:

#### **Axis 1: Severity Axis**
| Severity Level | Code | Description |
| :--- | :---: | :--- |
| **SAFE** | `0` | Clean, neutral opinion, standard remark, harmless joke, or constructive discussion. |
| **OFFENSIVE** | `1` | Vulgar words, curse words, rude tone, insults, or disrespectful mockery. |
| **HARMFUL** | `2` | Direct threats, incitement to violence, extreme harassment, or targeted hate speech. |

#### **Axis 2: Target Axis**
| Target Type | Code | Description |
| :--- | :---: | :--- |
| **NEITHER** | `0` | General remark, no specific target mentioned (or comment was SAFE). |
| **PERSON** | `1` | Targeted at a specific individual, commenter, creator, or public figure. |
| **INSTITUTION** | `2` | Targeted at an organization, private company, brand, political group, or government entity. |

#### **Optional Metadata**:
- **Contains PII**: Check this box if the comment contains sensitive Personal Identifiable Information (phone number, telegram handle, private address).
- **Notes**: Optional annotation memo for ambiguous cases.

---

### 3. Keyboard Shortcuts (Desktop)

For high-speed labeling, use your keyboard without touching the mouse:

| Key | Action |
| :---: | :--- |
| <kbd>1</kbd> | Select **SAFE (0)** |
| <kbd>2</kbd> | Select **OFFENSIVE (1)** |
| <kbd>3</kbd> | Select **HARMFUL (2)** |
| <kbd>Q</kbd> | Select **NEITHER (0)** |
| <kbd>W</kbd> | Select **PERSON (1)** |
| <kbd>E</kbd> | Select **INSTITUTION (2)** |
| <kbd>P</kbd> | Toggle **Contains PII** checkbox |
| <kbd>S</kbd> | **Skip** comment (returns it to queue) |
| <kbd>Enter</kbd> | **Submit & Next** (submits rating and claims next comment) |
| <kbd>H</kbd> | Open **History** modal |
| <kbd>M</kbd> | **Mute / Unmute** background music |
| <kbd>Esc</kbd> | Close any open modal |

---

### 4. Mobile Usage & Ergonomics

- **Side-by-Side 2-Column Design**:
  - Column 1: Severity options (`SAFE`, `OFFENSIVE`, `HARMFUL`)
  - Column 2: Target options (`NEITHER`, `PERSON`, `INSTITUTION`)
- **10-Line Khmer Comment Box**:
  - Displays 10 lines of Khmer text in Kantumruy Pro font.
  - If a comment is longer than 10 lines, swipe up/down inside the box to scroll smoothly.
  - Automatically resets to line 1 whenever a new comment is loaded.
- **Compact 32px Tap Buttons**:
  - Streamlined buttons with high-contrast color tints and tactile press feedback (`scale: 0.95`).
- **Zero Page Scroll**:
  - The entire interface fits completely within mobile screens (iPhone SE, iPhone 12/13/14/15, Android) without outer page scrolling.

---

### 5. Editing Previous Labels (History)

Made a mistake or changed your mind?
1. Click **📜 History** in the header (or press <kbd>H</kbd>).
2. Browse your recently annotated comments.
3. Click the **✏️ Edit** button on any comment.
4. An interactive modal pops up with your previous selection pre-loaded.
5. Modify the ratings and hit **Save Changes** (or press <kbd>Enter</kbd>).
6. Both dataset CSV files and your statistics update automatically.

---

### 6. Leaderboard & Exporting

- **🏆 Leaderboard**: Click **Leaderboard** in the header to view total progress, remaining comments, severity distribution percentages, and contributor rankings.
- **⬇️ Download CSV**: Click the **⬇️ CSV** button in the header anytime to download the fully updated dataset with all completed annotations.

---

## ⚙️ Technical Architecture

### Real-time Concurrency & Locking
```
User A (Browser) ----> [POST /api/claim] ----> Leased for 60s
User B (Browser) ----> [POST /api/claim] ----> Leased NEXT available comment
User A closes tab ---> [POST /api/release] --> Released immediately to queue
```

1. **Unique Comment Guarantee**:
   - Raw Facebook comments are deduplicated with strict unique IDs (`dom__0`, `dom__0_2`, etc.).
   - The queue only serves comments where `annotator` is empty.
2. **Fail-Safe Lease Expiration**:
   - Each leased comment has a 60-second lease with an active 15-second heartbeat timer.
   - If a user loses connection or powers off their device, the lease expires in 60s and becomes available for others.
3. **Atomic Dual-File Persistence**:
   - Saves are protected with Python threading locks (`threading.Lock`).
   - Every submission atomically updates:
     1. `scraper/raw_data/cleaned_comments.csv`
     2. `ai_engine/data/comments.csv`

---

## 📁 Directory Structure

```
scraper/labeling_app/
├── run.py                 # Core launcher (FastAPI + Cloudflare Tunnel detector)
├── run_server.sh          # One-click startup script for macOS / Linux
├── run_server.bat         # One-click startup script for Windows
├── server.py              # FastAPI backend API & data synchronization logic
├── README.md              # Documentation and user guide
├── sound/
│   └── lobby-classic-game.mp3  # Optional ambient background audio
└── static/
    ├── index.html         # Workspace markup & modal dialogs
    ├── style.css          # Modern dark-mode responsive styling system
    └── app.js             # Client application state & API interactions
```

---

## 🤝 Contributing & License
Maintained as part of the **KCMS (Khmer Comment Moderation System)** project. Developed for high-accuracy Khmer NLP dataset collection.
