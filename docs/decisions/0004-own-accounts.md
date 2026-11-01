# 4. Own accounts with email verification instead of SSO

*Date: 2026-10-30 · Status: Accepted*

## Context

v1 signed people in through Keycloak SSO (`sso.genomicsthailand.com`, realm `geth`), reused from Cohort Builder. That realm belongs to a research project whose members are mostly researchers, not Cloud staff, so it is the wrong directory for an internal portal. The portal has about 50 users.

## Decision

The portal keeps its own accounts, modelled on THEIA and Cohort Builder:

1. **Sign up with email and password.** Passwords are stored as PBKDF2-SHA256 hashes (600,000 rounds, random salt).
2. **Verify the address.** Sign-up emails a link (valid 2 days). Until it is opened, the account can't be approved or used.
3. **An admin approves** each account on the requests page (จัดการคำขอ, in the menu under the admin's name), where a count beside the name shows waiting sign-ups.
4. **Forgot password** emails a one-time link (valid 1 hour); admins can send someone the same link. No admin ever types or sees another person's password.
5. **Email is used only for those two things**: confirming an address at sign-up, and resetting a password. No approval, invitation or admin notification emails; people sign up themselves.
6. **Sign-up never shows whether an email already has an account**: the owner of that address is emailed instead.
7. **Ten wrong passwords in an hour lock the account for 20 minutes.** Suspending an account ends its sessions at once.
8. **Email goes out through plain SMTP**, so any provider works; we use Resend. Without SMTP settings (local development), emails are written to the server log.
9. **The first admin** comes from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`. `ALLOWED_EMAIL_DOMAINS` can limit sign-up to the organization's domains.

## Options considered

- **Keep Keycloak SSO (geth realm):** wrong directory, see above.
- **The organization's SSO:** possible later; nothing here prevents adding it as a second way in.
- **Admin-created accounts only, no email:** admins would have to choose and pass on passwords, and nobody could reset their own.

## Consequences

- The portal now stores password hashes, so the database backup must be protected like any credential store.
- Sign-up and password reset depend on the SMTP service; if it is down, existing users can still sign in.
- Sending from our own address needs a domain verified in Resend (SPF/DKIM DNS records).
