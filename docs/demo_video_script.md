# Hackathon Demo Video Script & Shot List

**Target Duration:** ~165 seconds (2 minutes 45 seconds; strictly under 3 minutes)  
**Track:** Personal AI — Nebius x NVIDIA Global AI Hackathon  
**Models & Infrastructure Mentioned Aloud:**
- **Nebius Token Factory**: Fast, serverless OpenAI-compatible inference API.
- **NVIDIA Nemotron Nano** (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`): Low-latency model for routine conversations, daily briefings, and tool extraction.
- **NVIDIA Nemotron Ultra** (`nvidia/Nemotron-3-Ultra-550b-a55b`): Deep reasoning model for high-complexity analysis, planning, and technical trade-offs.
- **Qwen3-Embedding-8B**: 1024-dimensional semantic embedding model powering hybrid SQLite memory recall.
- **SQLCipher AES-256 + scrypt KDF**: Zero-knowledge encrypted-at-rest personal database.

---

## Pre-Recording Checklist
- [ ] **No Secrets on Screen**: Never open `.env` or show `NEBIUS_API_KEY`. Browser and terminal windows should only show UI, logs, and Token Factory usage.
- [ ] **Demo Data Active**: Run `python seed_demo.py` prior to recording to load clean, fictitious sample memories.
- [ ] **Incognito Verification**: Ensure demo runs at `http://localhost:8000/ui/index.html` or deployed HTTPS URL cleanly in an incognito window.
- [ ] **Microphone & Audio**: Clear speech audio, no background hum; voice input/output feature tested.
- [ ] **Video Host**: Upload as Public or Unlisted on YouTube; verify URL works in an incognito tab.
- [ ] **Captions**: Enable YouTube auto-captions or upload transcript for accessibility.

---

## Timed Shot List & Narration Script

### Scene 1: Introduction & Architecture (0:00 - 0:25) ~25s
- **Visual / Shot:** Full screen of the assistant web UI (`http://localhost:8000/ui/index.html`). The sleek dark-mode interface shows the header with the Nano badge, the cost counter (`$0.0000`), and the Morning Brief button.
- **Spoken Narration (You):**
  > *"Welcome to the Private Personal Assistant with Persistent Memory, built for the Nebius and NVIDIA Global AI Hackathon in the Personal AI track.  
  > Most AI assistants upload all your thoughts to third-party clouds with zero local privacy. We built an assistant where your memory is truly yours: encrypted locally at rest with SQLCipher AES-256 derived from a user passphrase using scrypt.  
  > All model intelligence is powered by Nebius Token Factory, combining NVIDIA Nemotron models with 1024-dimensional embeddings."*

---

### Scene 2: Nano vs. Ultra Dynamic Model Routing (0:25 - 0:50) ~25s
- **Visual / Shot:** Type `"Hi! Give me a quick 1-sentence tip for productive mornings"` with model selector set to **nano**. Press Send. The assistant replies immediately. Point mouse to the green **`nano`** chip on the response and in the header badge. Then switch dropdown to **ultra** and send: `"Compare SQLCipher page-level encryption vs application-level field encryption in 2 sentences."` The response renders with the purple **`ultra`** chip.
- **Spoken Narration (You):**
  > *"We implement intelligent model routing between NVIDIA Nemotron models. For rapid everyday interactions, we query NVIDIA Nemotron Nano through Nebius Token Factory. Notice the instantaneous response and the green nano badge.  
  > For complex technical synthesis, we switch to NVIDIA Nemotron Ultra. Ultra reasons deeply through architectural trade-offs, automatically highlighted by our ultra badge, while our built-in daily spending cap ensures we never exceed our credit limits."*

---

### Scene 3: Persistent Memory Across Sessions & "Memories Used" (0:50 - 1:15) ~25s
- **Visual / Shot:** Type: `"Remember that I love drinking matcha green tea every morning before starting deep work."` Assistant confirms it stored the preference. Refresh the browser page or open a new browser tab to demonstrate persistence across sessions. Now ask: `"What should I prepare to drink before I start coding?"` The assistant answers `"Matcha green tea!"` and highlights the **`memories used`** chip beneath the response.
- **Spoken Narration (You):**
  > *"Here is persistent episodic memory in action across sessions. When I share a habit or personal fact, the assistant embeds it using Qwen-8B and writes it to our encrypted SQLite database.  
  > Even after refreshing the session or restarting the client, our hybrid recall engine retrieves that exact context. You can see the transparent 'memories used' chip right beneath the answer, showing judges exactly what retrieved data influenced the response."*

---

### Scene 4: Skill Engine & 2-Step Tool Confirmation (1:15 - 1:45) ~30s
- **Visual / Shot:** Type: `"Add a note: Submit Devpost project before October 30 deadline."` The assistant intercepts the Note skill, halts, and renders the interactive confirmation modal: *"Save note: 'Submit Devpost project before October 30 deadline.'?"* with **Confirm** and **Cancel** buttons. Point to it, explain why, then click **Confirm**. A green banner executes the change, confirms creation in SQLite, and logs it to `tool_audit_log`.
- **Spoken Narration (You):**
  > *"Personal assistants should never execute destructive or external actions without user agency. When our Skill Engine detects a tool intent—such as creating or modifying notes, calendar events, or sandboxed files—it proposes an action with a short-lived cryptographic ID.  
  > Nothing changes in storage until I explicitly review the proposed summary and click Confirm. Once verified, the action executes, returns an audit confirmation, and records a privacy-safe entry in the tool audit log."*

---

### Scene 5: Privacy Panel & Verifiable Hard Delete (1:45 - 2:15) ~30s
- **Visual / Shot:** Click on the cost counter in the top-right header or press `Ctrl+M` to open the slide-out **Memories Panel**. Scroll through the list of stored memory fragments, each tagged with provenance (`user_said`, `tool_output`). Click the **Delete** button next to a memory. Click OK on the browser prompt. The memory disappears instantly.
- **Spoken Narration (You):**
  > *"User privacy requires absolute transparency and verifiable data deletion. Opening our Memories Panel reveals every persisted memory with its provenance.  
  > When I click 'Delete', our backend doesn't just toggle a soft-delete flag—it executes a complete hard-delete. It removes the row, deletes the vector embedding, wipes the FTS5 search index, and cryptographically verifies that zero remnants exist in the database."*

---

### Scene 6: Nebius Token Factory Usage & Security Summary (2:15 - 2:45) ~30s
- **Visual / Shot:** Switch to browser tab displaying Nebius Token Factory Console (`https://tokenfactory.nebius.com/`) showing API usage, requests, and token tracking. Switch back to terminal to show the startup log `"encryption: on"` and `"HEALTHCHECK 200 OK"`.
- **Spoken Narration (You):**
  > *"Behind the scenes, Nebius Token Factory delivers lightning-fast token generation for our NVIDIA Nemotron and Qwen embedding models with complete OpenAI SDK compatibility.  
  > Only retrieved memory snippets and user prompts ever touch the inference API—your local database stays completely encrypted on disk with SQLCipher.  
  > Thank you to Nebius and NVIDIA for the fantastic developer platform. The code, test suite, and deployment guides are available on GitHub. Thank you for watching!"*

---

## Timetable Summary (165s Total)
| Timestamp | Segment | Key Feature Demonstrated |
|---|---|---|
| `0:00 - 0:25` (25s) | Intro & Security Overview | SQLCipher AES-256 + scrypt KDF, Nebius Token Factory |
| `0:25 - 0:50` (25s) | Nano vs Ultra Dynamic Routing | Nemotron Nano fast chat, Nemotron Ultra reasoning, UI badges |
| `0:50 - 1:15` (25s) | Persistent Memory & Recall | Qwen3 embeddings, cross-session recall, "memories used" chips |
| `1:15 - 1:45` (30s) | Skill Engine & Action Confirmation | NoteSkill, 2-step confirmation modal, audit logging |
| `1:45 - 2:15` (30s) | Privacy Panel & Hard-Delete | Memories list, provenance tags, verified hard-delete |
| `2:15 - 2:45` (30s) | Nebius Console & Conclusion | Token Factory usage, spend guard, GitHub repo |
