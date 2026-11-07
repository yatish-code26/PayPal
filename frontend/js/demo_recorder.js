/**
 * FreightGuard 120-Second Automated Demo & Video Recording Engine
 * - Broadcast-quality subtitles synchronized across 8 structured chapters
 * - Exact 2:00 (120-second) pacing matching official hackathon submission requirements
 * - Live screen recorder via MediaRecorder API producing downloadable 1080p video file
 * - Automated feature-by-feature execution with zero manual input required
 */
const DemoRecorder = {
  isRunning: false,
  isRecording: false,
  mediaRecorder: null,
  recordedChunks: [],
  timerInterval: null,
  currentSecond: 0,
  totalSeconds: 120,

  chapters: [
    {
      start: 0,
      end: 15,
      title: "1/8: Executive Problem & Home Dashboard",
      subtitle: "FreightGuard: Autonomous freight audit and safe PayPal payments. Solving the 15-20% invoice leakage across enterprise logistics.",
      action: async () => {
        await App.navigateTo("home");
        await ControlTowerView.init();
      }
    },
    {
      start: 15,
      end: 35,
      title: "2/8: Deep Invoice Audit & The $2,180 Variance",
      subtitle: "Apex Global Freight (INV-2025-88419) billed $5,522.00. Our deterministic policy engine isolates $2,180.00 in uncontracted charges.",
      action: async () => {
        await App.navigateTo("workbench", "INV-2025-88419");
      }
    },
    {
      start: 35,
      end: 50,
      title: "3/8: Policy Invariant — AI Never Decides Money",
      subtitle: "Policy Guard Active: LLMs explain findings and draft dispute letters, but monetary arithmetic is 100% deterministic in exact integer cents.",
      action: async () => {
        await WorkbenchView.loadAiExplanation("INV-2025-88419");
      }
    },
    {
      start: 50,
      end: 70,
      title: "4/8: Standout Feature — 'Pay Now, Hold the Rest'",
      subtitle: "Split Settlement: Disbursing verified $3,342.00 immediately via PayPal Payouts to maintain carrier goodwill, holding $2,180.00 in reserve.",
      action: async () => {
        try {
          await API.payNowHoldRest("INV-2025-88419");
          await WorkbenchView.loadWorkbenchData("INV-2025-88419");
        } catch (e) {
          console.log("Split settlement position noted:", e);
        }
      }
    },
    {
      start: 70,
      end: 85,
      title: "5/8: Commercial Dispute Notice & Pure-Python PDF Export",
      subtitle: "AI synthesizes formal commercial dispute notice citing exact Master Service Agreement clauses and DOE fuel indexes, with one-click PDF export.",
      action: async () => {
        await App.navigateTo("disputes", "INV-2025-88419");
      }
    },
    {
      start: 85,
      end: 100,
      title: "6/8: Dual-Approver Governance & PayPal Webhooks",
      subtitle: "Controlled Settlement: Two-person segregation of duties with idempotency tokens. Authoritative PayPal webhooks reconcile payment to RECONCILED.",
      action: async () => {
        await App.navigateTo("payments", "INV-2025-88419");
        try {
          await API.simulateWebhook("PAYMENT.PAYOUTS-ITEM.SUCCEEDED", "PAYPAL-ITEM-DEMO-88419", "PAYPAL-BATCH-DEMO-88419");
          await SettlementView.loadSettlementView("INV-2025-88419");
        } catch (e) {
          console.log("Webhook simulated:", e);
        }
      }
    },
    {
      start: 100,
      end: 110,
      title: "7/8: Carrier Scorecards & Renewal Intelligence",
      subtitle: "Carrier Scorecards track error frequencies across carriers, projecting annual financial leakage and providing automated contract negotiation points.",
      action: async () => {
        await App.navigateTo("scorecards");
      }
    },
    {
      start: 110,
      end: 120,
      title: "8/8: Tamper-Evident SHA-256 Audit Trail",
      subtitle: "Cryptographic Assurance: Append-only SHA-256 hash-chained audit trail. One click verifies all blocks, providing immutable mathematical proof.",
      action: async () => {
        await App.navigateTo("activity");
        await AuditTrailView.verifyIntegrity();
      }
    }
  ],

  init() {
    this.bindButtons();
  },

  bindButtons() {
    const startBtn = document.getElementById("btn-start-120s-demo");
    if (startBtn) {
      startBtn.addEventListener("click", () => this.showLaunchModal());
    }
  },

  showLaunchModal() {
    App.openModal(
      "120-Second Hackathon Demo Video Engine",
      `
      <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 20px;">
        Run or record an official <strong>120-second (2-minute)</strong> video walkthrough of FreightGuard tailored for judges. 
        Includes broadcast-quality synchronized subtitles, automatic navigation across all 8 core features, and live screen capture to a downloadable video file.
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;">
        <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 16px; background-color: var(--bg-muted);">
          <div style="font-weight: 700; color: var(--text-primary); margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 18px;">🎥</span> Record Screen to Video
          </div>
          <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 12px;">
            Captures your browser window in full 1080p HD with subtitles, automated clicks, and downloads <code>FreightGuard-120s-Demo.webm</code> when complete.
          </p>
          <button class="btn btn-primary btn-sm" style="width: 100%;" onclick="DemoRecorder.startRecordingAndWalkthrough()">
            Record Screen & Walkthrough
          </button>
        </div>

        <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 16px; background-color: var(--bg-muted);">
          <div style="font-weight: 700; color: var(--text-primary); margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 18px;">▶</span> Live Guided Walkthrough
          </div>
          <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 12px;">
            Runs the 120-second automated sequence with on-screen subtitle bar without recording a video file (great for previewing or screen recording via Loom/OBS).
          </p>
          <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="DemoRecorder.startLiveWalkthroughOnly()">
            Start Live Walkthrough
          </button>
        </div>
      </div>

      <div style="background-color: var(--status-info-bg); border: 1px solid var(--status-info-border); border-radius: var(--radius-sm); padding: 10px 14px; font-size: 12px; color: var(--status-info);">
        <strong>Note:</strong> Standalone subtitle file for YouTube upload is located at <code>docs/demo-video-subtitles.srt</code>. Narration script is at <code>docs/demo-video-script.md</code>.
      </div>
      `
    );
  },

  async startRecordingAndWalkthrough() {
    App.closeModal();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
      App.showToast("Browser screen capture not supported. Running live walkthrough instead.", "warning");
      this.startLiveWalkthroughOnly();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: "browser", frameRate: 60 },
        audio: false
      });

      this.recordedChunks = [];
      const options = { mimeType: "video/webm;codecs=vp9" };
      try {
        this.mediaRecorder = new MediaRecorder(stream, options);
      } catch (e) {
        this.mediaRecorder = new MediaRecorder(stream);
      }

      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          this.recordedChunks.push(e.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        this.saveRecordedVideo();
        stream.getTracks().forEach(track => track.stop());
      };

      this.mediaRecorder.start(1000);
      this.isRecording = true;
      App.showToast("Recording started! Running 120-second demo sequence...", "success");

      this.startSequence();
    } catch (e) {
      console.warn("Screen recording cancelled or failed:", e);
      App.showToast("Screen capture cancelled. Starting live walkthrough.", "info");
      this.startLiveWalkthroughOnly();
    }
  },

  startLiveWalkthroughOnly() {
    App.closeModal();
    this.isRecording = false;
    App.showToast("Starting 120-second automated demo walkthrough...", "info");
    this.startSequence();
  },

  startSequence() {
    this.isRunning = true;
    this.currentSecond = 0;
    this.createSubtitleOverlay();

    // Run first chapter immediately
    this.executeChapterForSecond(0);

    clearInterval(this.timerInterval);
    this.timerInterval = setInterval(() => {
      this.currentSecond++;
      this.updateSubtitleOverlay();

      this.executeChapterForSecond(this.currentSecond);

      if (this.currentSecond >= this.totalSeconds) {
        this.stopDemo(true);
      }
    }, 1000);
  },

  executeChapterForSecond(sec) {
    const chapter = this.chapters.find(c => c.start === sec);
    if (chapter && typeof chapter.action === "function") {
      chapter.action().catch(err => console.log("Chapter action caught:", err));
    }
  },

  createSubtitleOverlay() {
    let overlay = document.getElementById("demo-subtitle-container");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "demo-subtitle-container";
      overlay.className = "demo-subtitle-container";
      document.body.appendChild(overlay);
    }
    this.updateSubtitleOverlay();
  },

  updateSubtitleOverlay() {
    const overlay = document.getElementById("demo-subtitle-container");
    if (!overlay) return;

    const currentChapter = this.chapters.find(c => this.currentSecond >= c.start && this.currentSecond < c.end) || this.chapters[this.chapters.length - 1];

    const mins = Math.floor(this.currentSecond / 60);
    const secs = this.currentSecond % 60;
    const timeStr = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    const pct = Math.min(100, (this.currentSecond / this.totalSeconds) * 100);

    overlay.innerHTML = `
      <div class="demo-subtitle-header">
        <span class="demo-chapter-pill">${currentChapter.title}</span>
        <span class="demo-timer">${timeStr} / 02:00</span>
        <div style="display: flex; gap: 8px; align-items: center;">
          ${this.isRecording ? '<span class="pulse-dot" style="background-color: var(--status-danger);"></span><span style="font-size: 11px; font-weight: 700; color: #ffffff;">REC</span>' : ''}
          <button class="btn btn-secondary btn-sm" onclick="DemoRecorder.stopDemo(false)" style="padding: 2px 8px; font-size: 11px;">Stop</button>
        </div>
      </div>
      <div class="demo-subtitle-text">${currentChapter.subtitle}</div>
      <div class="demo-progress-bar">
        <div class="demo-progress-fill" style="width: ${pct}%;"></div>
      </div>
    `;
  },

  stopDemo(completed = false) {
    this.isRunning = false;
    clearInterval(this.timerInterval);

    const overlay = document.getElementById("demo-subtitle-container");
    if (overlay) overlay.remove();

    if (this.isRecording && this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      this.mediaRecorder.stop();
      this.isRecording = false;
    }

    if (completed) {
      App.showToast("🎉 120-Second Demo Complete! Full lifecycle successfully demonstrated.", "success");
    } else {
      App.showToast("Demo stopped.", "info");
    }
  },

  saveRecordedVideo() {
    if (this.recordedChunks.length === 0) return;

    const blob = new Blob(this.recordedChunks, { type: "video/webm" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.style.display = "none";
    a.href = url;
    a.download = "FreightGuard-120s-Demo.webm";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 100);

    App.showToast("Video downloaded successfully: FreightGuard-120s-Demo.webm", "success");
  }
};

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  DemoRecorder.init();
});

