"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "primereact/button";
import { Menu } from "primereact/menu";
import type { MenuItem } from "primereact/menuitem";
import { api } from "@/lib/api";
import type { Me } from "@/lib/types";
import { SessionProvider, useSession } from "@/lib/session";
import AuthBackground, { HeaderDots } from "./AuthBackground";
import ChangePassword from "./ChangePassword";
import SignIn from "./SignIn";

type NavItem = { href: string; label: string; active: boolean };

/** The portal's name, or (`short`) a "DP" tile where the full name doesn't fit. */
function Brand({ short = false, tabIndex }: { short?: boolean; tabIndex?: number }) {
  if (short) {
    return (
      <Link href="/" tabIndex={tabIndex} aria-label="Developer Portal" title="Developer Portal"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/5 ring-1 ring-white/20">
        <span className="metal-silver font-mono text-sm font-semibold">DP</span>
      </Link>
    );
  }
  return (
    <Link href="/" tabIndex={tabIndex} className="metal-silver min-w-0 truncate whitespace-nowrap font-mono text-lg font-semibold">
      Developer Portal
    </Link>
  );
}

function NavLinks({ nav, vertical = false, tabIndex }: { nav: NavItem[]; vertical?: boolean; tabIndex?: number }) {
  return (
    <nav className={vertical ? "flex flex-col gap-1" : "flex gap-1.5"} aria-label={tabIndex === -1 ? undefined : "เมนูหลัก"}>
      {nav.map((n) => (
        <Link
          key={n.href}
          href={n.href}
          tabIndex={tabIndex}
          aria-current={n.active ? "page" : undefined}
          className={`whitespace-nowrap rounded-md px-4 py-2 text-base ${n.active ? "bg-white/10 font-medium text-white ring-1 ring-white/15" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}
        >
          {n.label}
        </Link>
      ))}
    </nav>
  );
}

// The count of sign-ups waiting for approval.
function WaitingBadge({ count }: { count: number }) {
  if (!count) return null;
  return (
    <span className="rounded-full bg-amber-400 px-2 py-0.5 text-xs font-semibold text-slate-900" aria-label={`${count} คำขอรออนุมัติ`}>
      {count}
    </span>
  );
}

/** An admin's name and badge open the admin pages. */
function AdminMenu({ me, waiting, tabIndex }: { me: Me; waiting: number; tabIndex?: number }) {
  const menu = useRef<Menu>(null);
  const router = useRouter();
  const go = (href: string) => () => router.push(href);
  const items: MenuItem[] = [
    { label: "ผู้ใช้", icon: "pi pi-users", command: go("/users/") },
    {
      // A custom layout, for the count badge. It keeps PrimeReact's own wrapper and
      // classes so it lines up with the other items. `command` serves the keyboard
      // (Enter on the focused item); a mouse click navigates here.
      label: "จัดการคำขอ", icon: "pi pi-inbox", command: go("/requests/"),
      template: (item, options) => (
        <div className="p-menuitem-content">
          <a href="/requests/" tabIndex={-1} className={`${options.className} flex items-center`}
            onClick={(e) => { e.preventDefault(); menu.current?.hide(e); router.push("/requests/"); }}>
            <span className={options.iconClassName} />
            <span className={options.labelClassName}>{item.label}</span>
            {/* Negative margin: the badge mustn't make this row taller than the others. */}
            <span className="-my-1 ml-auto pl-3 leading-none"><WaitingBadge count={waiting} /></span>
          </a>
        </div>
      ),
    },
    { label: "ประวัติการใช้งาน", icon: "pi pi-history", command: go("/activity/") },
  ];
  return (
    <>
      <button type="button" tabIndex={tabIndex} onClick={(e) => menu.current?.toggle(e)} aria-haspopup="menu"
        className="flex items-center gap-2 rounded-md px-3 py-1.5 text-slate-300 hover:bg-white/5 hover:text-white">
        {me.name}
        <span className="rounded bg-white/10 px-2 py-0.5 text-sm ring-1 ring-white/15">ผู้ดูแลระบบ</span>
        <WaitingBadge count={waiting} />
        <i className="pi pi-chevron-down text-xs" aria-hidden />
      </button>
      <Menu model={items} popup ref={menu} popupAlignment="right" />
    </>
  );
}

function UserArea({ me, waiting, signOut, tabIndex }: { me: Me; waiting: number; signOut: () => void; tabIndex?: number }) {
  return (
    <div className="flex items-center gap-4 whitespace-nowrap text-base">
      {me.is_admin ? <AdminMenu me={me} waiting={waiting} tabIndex={tabIndex} /> : <span className="text-slate-300">{me.name}</span>}
      <ChangePassword tabIndex={tabIndex} />
      <Button icon={<PowerIcon />} text rounded className="!text-slate-200" onClick={signOut} tabIndex={tabIndex}
        aria-label="ออกจากระบบ" tooltip="ออกจากระบบ" tooltipOptions={{ position: "bottom" }} />
    </div>
  );
}

// Lucide's "power" icon (lucide.dev/icons/power, ISC licence), sized like the primeicons beside it.
function PowerIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 2v10" />
      <path d="M18.4 6.6a9 9 0 1 1-12.77.04" />
    </svg>
  );
}

function Header() {
  const { me, signOut } = useSession();
  const pathname = usePathname();
  const nav: NavItem[] = [
    { href: "/", label: "แดชบอร์ด", active: pathname === "/" },
    { href: "/systems/", label: "ระบบทั้งหมด", active: pathname.startsWith("/system") },
    { href: "/new/", label: "ลงทะเบียนระบบ", active: pathname.startsWith("/new") },
  ];

  // Admins see how many sign-ups wait for them, refreshed on every page change.
  const [waiting, setWaiting] = useState(0);
  useEffect(() => {
    if (!me.is_admin) return;
    api<{ count: number }>("/api/admin/users/pending-count").then((r) => setWaiting(r.count)).catch(() => undefined);
  }, [me.is_admin, pathname]);

  // How much of the header fits on one row: everything with the full name;
  // everything with the "DP" tile instead; or, failing both, the name and a
  // menu button. Invisible copies of the two one-row layouts are measured
  // against the space available, on every resize, so the switch happens exactly
  // where the row would otherwise wrap, whatever the user's name or the fonts.
  const rowRef = useRef<HTMLDivElement>(null);
  const fullRef = useRef<HTMLDivElement>(null);
  const shortRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<"full" | "short" | "menu">("full");
  useEffect(() => {
    const row = rowRef.current;
    const full = fullRef.current;
    const short = shortRef.current;
    if (!row || !full || !short) return;
    const observer = new ResizeObserver(() => {
      const available = row.clientWidth - parseFloat(getComputedStyle(row).paddingLeft) * 2;
      setLayout(full.scrollWidth <= available ? "full" : short.scrollWidth <= available ? "short" : "menu");
    });
    observer.observe(row);
    observer.observe(full);
    observer.observe(short);
    return () => observer.disconnect();
  }, []);
  const compact = layout === "menu";

  // The menu is open for the page it was opened on, so going to another page closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = compact && openOn === pathname;
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent) {
        if (e.key !== "Escape") return;
        buttonRef.current?.focus();
      } else if (panelRef.current?.contains(e.target as Node) || buttonRef.current?.contains(e.target as Node)) {
        return;
      }
      setOpenOn(null);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("mousedown", close);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("mousedown", close);
    };
  }, [open]);

  return (
    // Deep navy space, like the sign-in page. It stays at the top while the page
    // scrolls (see .site-header in globals.css).
    <header className="site-header text-white">
      <HeaderDots />

      {/* Invisible copies of the one-row layouts, only for measuring. They sit in a
          zero-size clipped box, so their width never makes the page scroll sideways. */}
      <div className="pointer-events-none invisible absolute left-0 top-0 h-0 w-0 overflow-hidden" aria-hidden>
        {[{ ref: fullRef, short: false }, { ref: shortRef, short: true }].map(({ ref, short }) => (
          <div key={String(short)} ref={ref} className="flex w-max items-center gap-x-6">
            <Brand short={short} tabIndex={-1} />
            <NavLinks nav={nav} tabIndex={-1} />
            <UserArea me={me} waiting={waiting} signOut={signOut} tabIndex={-1} />
          </div>
        ))}
      </div>

      <div ref={rowRef} className={`relative mx-auto flex max-w-7xl items-center px-4 py-4 ${compact ? "gap-x-4" : "gap-x-6"}`}>
        <Brand short={layout === "short"} />
        {compact ? (
          <button
            ref={buttonRef}
            type="button"
            onClick={() => setOpenOn(open ? null : pathname)}
            aria-expanded={open}
            aria-controls="site-menu"
            aria-label={open ? "ปิดเมนู" : "เปิดเมนู"}
            className="ml-auto flex h-11 w-11 items-center justify-center rounded-md text-slate-200 ring-1 ring-white/15 hover:bg-white/10"
          >
            <i className={`pi ${open ? "pi-times" : "pi-bars"} text-lg`} aria-hidden />
          </button>
        ) : (
          <>
            <NavLinks nav={nav} />
            <div className="ml-auto"><UserArea me={me} waiting={waiting} signOut={signOut} /></div>
          </>
        )}
      </div>

      {open && (
        <div id="site-menu" ref={panelRef} className="site-menu-panel absolute inset-x-0 top-full">
          <div className="mx-auto max-w-7xl space-y-3 px-4 py-4">
            <NavLinks nav={nav} vertical />
            <div className="border-t border-white/10 pt-3"><UserArea me={me} waiting={waiting} signOut={signOut} /></div>
          </div>
        </div>
      )}
    </header>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider signIn={(props) => <SignIn {...props} />}>
      {/* The sign-in page's dot pattern, flipped: black dots on plain white, fixed behind every page. */}
      <div className="fixed inset-0 z-0 overflow-hidden bg-white" aria-hidden>
        <AuthBackground tone="light" />
      </div>
      <Header />
      <main className="relative z-10 mx-auto max-w-7xl px-4 py-6">{children}</main>
    </SessionProvider>
  );
}
