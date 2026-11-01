"use client";

import { useEffect, useState } from "react";
import { Button } from "primereact/button";
import { InputText } from "primereact/inputtext";
import { Password } from "primereact/password";
import WarpPortal from "./WarpPortal";
import { Message } from "primereact/message";
import { api, ApiError } from "@/lib/api";
import type { AuthConfig } from "@/lib/session";
import AuthBackground, { setTwinkleSpeed } from "./AuthBackground";

type Props = {
  config: AuthConfig | null;
  onSignedIn: () => void;
  error: string | null;
};

// The two lines of the title. Each reveals one character width at a time behind
// a cursor, so letters appear exactly where the cursor is. This relies on the
// monospaced code font: every character is 1ch wide. The cursor types the first
// line, then moves to the second and keeps blinking there.
const TITLE_LINES = [
  { text: "T2Gen", className: "text-7xl font-semibold", seconds: 0.8, delay: 0.3 },
  { text: "Developer Portal", className: "text-4xl", seconds: 1.8, delay: 1.3 },
];

function TypedTitle() {
  return (
    <div className="metal-text font-mono leading-tight">
      {TITLE_LINES.map((line, i) => (
        <div key={line.text} className={line.className}>
          <span
            className={`typewriter-line ${i === TITLE_LINES.length - 1 ? "typewriter-cursor-stays" : "typewriter-cursor-passes"}`}
            style={{
              "--tw-chars": line.text.length,
              "--tw-seconds": `${line.seconds}s`,
              "--tw-delay": `${line.delay}s`,
            } as React.CSSProperties}
          >
            {line.text}
          </span>
        </div>
      ))}
    </div>
  );
}

// Hovering a sign-in button makes the background's stars twinkle six times as fast
// (as fast as before their normal speed was doubled).
const starsFast = { onMouseEnter: () => setTwinkleSpeed(6), onMouseLeave: () => setTwinkleSpeed(1) };

// "reset" sets a new password from an emailed link; "notice" is a message with a way back to sign in.
type Mode = "signin" | "signup" | "forgot" | "reset" | "notice";
type Flash = { severity: "success" | "info" | "warn" | "error"; text: string };

const HEADINGS: Record<Mode, { heading: string; intro: string }> = {
  signin: { heading: "เข้าสู่ระบบ", intro: "ใช้อีเมลและรหัสผ่านของคุณ" },
  signup: { heading: "สมัครใช้งาน", intro: "เราจะส่งลิงก์ไปยืนยันอีเมล จากนั้นผู้ดูแลระบบจะอนุมัติบัญชีของคุณ" },
  forgot: { heading: "ลืมรหัสผ่าน", intro: "กรอกอีเมลของคุณ เราจะส่งลิงก์สำหรับตั้งรหัสผ่านใหม่ไปให้" },
  reset: { heading: "ตั้งรหัสผ่านใหม่", intro: "ตั้งรหัสผ่านอย่างน้อย 8 ตัวอักษร" },
  notice: { heading: "ตรวจสอบอีเมลของคุณ", intro: "" },
};

const SUBMIT_LABEL: Record<Mode, string> = {
  signin: "เข้าสู่ระบบ", signup: "สมัครใช้งาน", forgot: "ส่งลิงก์", reset: "ตั้งรหัสผ่าน", notice: "",
};

type LinkTokens = { verify: string | null; reset: string | null };
let linkTokens: LinkTokens | null = null;

/** ?verify= or ?reset= from an emailed link. Read once, then taken off the
    address, so a reload doesn't reuse the link. */
function takeLinkTokens(): LinkTokens {
  if (linkTokens) return linkTokens;
  if (typeof window === "undefined") return { verify: null, reset: null };
  const params = new URLSearchParams(window.location.search);
  linkTokens = { verify: params.get("verify"), reset: params.get("reset") };
  if (linkTokens.verify || linkTokens.reset) window.history.replaceState(null, "", window.location.pathname);
  return linkTokens;
}

// How often the title types itself out again, and how long the old one takes
// to fade away first (matches .title-fading in globals.css).
const RETYPE_EVERY_MS = 60_000;
const FADE_OUT_MS = 1400;

export default function SignIn({ config, onSignedIn, error }: Props) {
  // Bumped every minute; used as the title's key, so React rebuilds the title
  // and its typing animation (and the reflection's) starts over. The old title
  // fades out first, so it doesn't vanish all at once.
  const [typeRun, setTypeRun] = useState(0);
  const [fading, setFading] = useState(false);
  useEffect(() => {
    let restart: ReturnType<typeof setTimeout> | undefined;
    const timer = setInterval(() => {
      setFading(true);
      restart = setTimeout(() => {
        setTypeRun((n) => n + 1);
        setFading(false);
      }, FADE_OUT_MS);
    }, RETYPE_EVERY_MS);
    return () => {
      clearInterval(timer);
      clearTimeout(restart);
    };
  }, []);

  const [link] = useState(takeLinkTokens);
  const [mode, setMode] = useState<Mode>(link.reset ? "reset" : "signin");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [flash, setFlash] = useState<Flash | null>(error ? { severity: "warn", text: error } : null);
  const [unverified, setUnverified] = useState(false);
  const [busy, setBusy] = useState(false);
  const { heading, intro } = HEADINGS[mode];

  function switchTo(next: Mode, message: Flash | null = null) {
    setMode(next);
    setFlash(message);
    setUnverified(false);
    setPassword("");
    setConfirm("");
  }

  // Arriving from an emailed "verify your address" link.
  useEffect(() => {
    if (link.verify) {
      api<{ status: string }>("/api/auth/verify-email", { method: "POST", body: { token: link.verify } })
        .then(({ status }) => status === "active"
          ? switchTo("signin", { severity: "success", text: "ยืนยันอีเมลแล้ว เข้าสู่ระบบได้เลย" })
          : switchTo("notice", { severity: "success",
              text: "ยืนยันอีเมลแล้ว ตอนนี้บัญชีของคุณรอผู้ดูแลระบบอนุมัติ เข้าสู่ระบบได้หลังจากได้รับอนุมัติ" }))
        .catch((e: Error) => switchTo("signin", { severity: "error", text: e.message }));
    }
  }, [link.verify]);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setFlash(null);
    setUnverified(false);
    try {
      await work();
    } catch (err) {
      setFlash({ severity: "error", text: (err as Error).message });
      setUnverified(err instanceof ApiError && err.code === "unverified");
    } finally {
      setBusy(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if ((mode === "signup" || mode === "reset") && password !== confirm) {
      setFlash({ severity: "error", text: "รหัสผ่านทั้งสองช่องไม่ตรงกัน" });
      return;
    }
    run(async () => {
      if (mode === "signin") {
        await api("/api/auth/login", { method: "POST", body: { email, password } });
        onSignedIn();
      } else if (mode === "signup") {
        await api("/api/auth/register", { method: "POST", body: { name, email, password } });
        switchTo("notice", { severity: "info",
          text: `เราส่งลิงก์ยืนยันไปที่ ${email} แล้ว กดลิงก์ในอีเมลเพื่อยืนยัน จากนั้นรอผู้ดูแลระบบอนุมัติ (ถ้าไม่เห็นอีเมล ลองดูในโฟลเดอร์สแปม)` });
      } else if (mode === "forgot") {
        await api("/api/auth/forgot-password", { method: "POST", body: { email } });
        switchTo("notice", { severity: "info",
          text: `ถ้า ${email} มีบัญชีอยู่ เราได้ส่งลิงก์สำหรับตั้งรหัสผ่านใหม่ไปแล้ว ลิงก์ใช้ได้ 1 ชั่วโมง` });
      } else if (mode === "reset") {
        const { status } = await api<{ status: string }>("/api/auth/reset-password",
          { method: "POST", body: { token: link.reset, password } });
        if (status === "active") switchTo("signin", { severity: "success", text: "ตั้งรหัสผ่านแล้ว เข้าสู่ระบบด้วยรหัสผ่านใหม่ได้เลย" });
        else switchTo("notice", { severity: "success", text: "ตั้งรหัสผ่านแล้ว บัญชีของคุณรอผู้ดูแลระบบอนุมัติ" });
      }
    });
  }

  function resendVerification() {
    run(async () => {
      await api("/api/auth/resend-verification", { method: "POST", body: { email } });
      setFlash({ severity: "info", text: "ส่งลิงก์ยืนยันอีกครั้งแล้ว (ส่งได้นาทีละครั้ง)" });
    });
  }

  const domains = config?.allowed_email_domains ?? [];
  const passwordField = (label: string, value: string, set: (v: string) => void, autoComplete: string) => (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <Password value={value} onChange={(e) => set(e.target.value)} feedback={false} toggleMask required
        autoComplete={autoComplete} className="mt-1 w-full" inputClassName="w-full" />
    </label>
  );

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#090a11] px-4 py-10 sm:px-8">
      <AuthBackground />

      {/* The card floats over the background, smaller than the screen so the background frames it. */}
      <div className="relative w-full max-w-6xl">
        {/* Light shining from behind the card's top-right corner (wide screens only). */}
        <div className="auth-backlight hidden lg:block" aria-hidden>
          <span className="backlight-blob backlight-haze" />
          <span className="backlight-blob backlight-heart" />
          <span className="backlight-blob backlight-spill-top" />
          <span className="backlight-blob backlight-spill-right" />
        </div>

        <div className="auth-card relative grid w-full overflow-hidden rounded-2xl bg-white lg:min-h-[40rem] lg:grid-cols-2">
          {/* Left half: Sign in or Sign up. The view swaps in place, with a short fade. */}
          <div className="flex flex-col px-6 py-8 sm:px-12">
            {/* On small screens the right half is hidden, so the name shows here instead. */}
            <div className="flex items-center gap-2 font-semibold tracking-wide text-navy lg:hidden">
              <i className="pi pi-sitemap" aria-hidden />
              T2Gen Developer Portal
            </div>

            <div key={mode} className="auth-view mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
              <h1 className="text-2xl font-semibold text-slate-900">{heading}</h1>
              {intro && <p className="mt-2 text-slate-600">{intro}</p>}

              {flash && <Message severity={flash.severity} text={flash.text} className="mt-6 w-full justify-start" />}
              {unverified && (
                <Button type="button" label="ส่งลิงก์ยืนยันอีกครั้ง" icon="pi pi-envelope" text size="small"
                  onClick={resendVerification} disabled={busy} className="mt-2" />
              )}

              {mode !== "notice" && (
                <form onSubmit={submit} className="mt-6 space-y-4">
                  {mode === "signup" && (
                    <label className="block text-sm font-medium text-slate-700">
                      ชื่อ-นามสกุล
                      <InputText value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" className="mt-1 w-full" />
                    </label>
                  )}
                  {mode !== "reset" && (
                    <label className="block text-sm font-medium text-slate-700">
                      อีเมล
                      {mode === "signup" && domains.length > 0 && (
                        <span className="font-normal text-slate-400"> (เฉพาะ {domains.map((d) => `@${d}`).join(", ")})</span>
                      )}
                      <InputText value={email} onChange={(e) => setEmail(e.target.value)} type="email" required autoComplete="email" className="mt-1 w-full" />
                    </label>
                  )}
                  {mode === "signin" && passwordField("รหัสผ่าน", password, setPassword, "current-password")}
                  {(mode === "signup" || mode === "reset") && (
                    <>
                      {passwordField("รหัสผ่าน (อย่างน้อย 8 ตัวอักษร)", password, setPassword, "new-password")}
                      {passwordField("ยืนยันรหัสผ่าน", confirm, setConfirm, "new-password")}
                    </>
                  )}
                  {mode === "signin" && (
                    <div className="-mt-2 text-right">
                      <button type="button" onClick={() => switchTo("forgot")} className="text-sm text-slate-600 underline-offset-2 hover:underline">
                        ลืมรหัสผ่าน?
                      </button>
                    </div>
                  )}
                  <Button type="submit" label={SUBMIT_LABEL[mode]} loading={busy} className="metal-button w-full" {...starsFast} />
                </form>
              )}

              <p className="mt-6 text-center text-sm text-slate-600">
                {mode === "signin" ? (
                  <>
                    เพิ่งเริ่มใช้พอร์ทัล?{" "}
                    <button type="button" onClick={() => switchTo("signup")} className="font-semibold text-slate-900 underline-offset-2 hover:underline">
                      สมัครใช้งาน
                    </button>
                  </>
                ) : (
                  <button type="button" onClick={() => switchTo("signin")} className="font-semibold text-slate-900 underline-offset-2 hover:underline">
                    กลับไปหน้าเข้าสู่ระบบ
                  </button>
                )}
              </p>
            </div>

            <div className="text-xs text-slate-400">
              <p>T2Gen IT · สำหรับใช้งานภายในเท่านั้น</p>
              {config?.support_email && (
                <div className="mt-2 flex items-center gap-3">
                  <span>ติดต่อผู้ดูแลระบบ</span>
                  {/* mailto: opens the person's own mail app with the address filled in. */}
                  <a href={`mailto:${config.support_email}`} title={`อีเมล ${config.support_email}`}
                    aria-label="ส่งอีเมลถึงผู้ดูแลระบบ" className="opacity-80 hover:opacity-100">
                    <img src="/mail.png" alt="" width={20} height={15} />
                  </a>
                  {/* Opens a Webex chat with the admin in the person's installed Webex app. */}
                  {/* Not URL-encoded: Webex reads "%40" literally instead of "@". */}
                  <a href={`webexteams://im?email=${config.support_email}`}
                    title={`Webex ${config.support_email}`} aria-label="แชทกับผู้ดูแลระบบทาง Webex"
                    className="opacity-80 hover:opacity-100">
                    {/* Webex logo from dashboardicons.com (homarr-labs/dashboard-icons). */}
                    <img src="/webex.svg" alt="" width={20} height={15} />
                  </a>
                </div>
              )}
            </div>
          </div>

          {/* Right half: the portal's name, typed out on a plate of metallic black, with a
              mirror reflection beneath. Hidden on small screens. */}
          <div className="metal-panel hidden flex-col justify-end px-12 pb-20 text-white lg:flex">
            {/* A small black hole turning in the empty top-right corner. */}
            <WarpPortal className="absolute right-8 top-10 w-64 xl:w-80" />
            <h2 className="sr-only">T2Gen Developer Portal</h2>
            <div aria-hidden key={typeRun} className={`title-retype ${fading ? "title-fading" : ""}`}>
              <TypedTitle />
              <div className="typewriter-reflection">
                <TypedTitle />
              </div>
            </div>
          </div>

          {/* Light from behind catching the card's top and right edges near the corner. */}
          <div className="auth-rim hidden lg:block" aria-hidden />
        </div>
      </div>
    </div>
  );
}
