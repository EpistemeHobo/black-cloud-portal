"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Toast } from "primereact/toast";
import { api } from "./api";
import type { Me, Meta } from "./types";
import { choiceLabel } from "./labels";

type SessionValue = {
  me: Me;
  meta: Meta;
  /** The Thai display label for a stored English value, or the value itself. */
  label: (value: string) => string;
  notify: (severity: "success" | "error" | "info", summary: string, detail?: string) => void;
  signOut: () => Promise<void>;
  /** Passwords live in Cognito, so the portal's own password screens are hidden. */
  cognito: boolean;
};

const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

export type AuthConfig = { support_email: string; allowed_email_domains: string[]; cognito: boolean; cognito_logout_url: string | null };

export function SessionProvider({ children, signIn }: {
  children: React.ReactNode;
  signIn: (props: { config: AuthConfig | null; onSignedIn: () => void; error: string | null }) => React.ReactNode;
}) {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useRef<Toast>(null);

  const load = useCallback(() => {
    Promise.all([api<{ person: Me | null }>("/api/auth/me"), api<AuthConfig>("/api/auth/config")])
      .then(async ([{ person }, cfg]) => {
        setConfig(cfg);
        if (person) setMeta(await api<Meta>("/api/meta"));
        setMe(person);
      })
      .catch(() => {
        setError("พอร์ทัลเชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาลองใหม่อีกครั้งในอีกสักครู่");
        setMe(null);
      });
  }, []);

  useEffect(load, [load]);

  const notify = useCallback<SessionValue["notify"]>((severity, summary, detail) => {
    toast.current?.show({ severity, summary, detail, life: severity === "error" ? 6000 : 3000 });
  }, []);

  const signOut = useCallback(async () => {
    const { logout_url } = await api<{ logout_url: string | null }>("/api/auth/logout", { method: "POST" });
    // A full reload on purpose, so no signed-in state is left in memory.
    // With Cognito, through its sign-out page, which comes back here.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = logout_url ?? "/";
  }, []);

  const label = useCallback((value: string) => choiceLabel(meta, value), [meta]);

  if (me === undefined) {
    return <div className="min-h-screen bg-white p-8 text-slate-500">กำลังโหลด…</div>;
  }
  return (
    <>
      <Toast ref={toast} position="bottom-right" />
      {me && meta ? (
        <SessionContext.Provider value={{ me, meta, label, notify, signOut, cognito: config?.cognito ?? false }}>{children}</SessionContext.Provider>
      ) : (
        signIn({ config, onSignedIn: load, error })
      )}
    </>
  );
}
