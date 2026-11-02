# 8. Sign-in with Cognito

*Date: 2026-11-02 · Status: Accepted*

## Context

Decision 0004 gave the portal its own accounts, so it stores password hashes and needs an email service to confirm addresses. On AWS the stack has no such service: verification links only reached the log, so nobody could finish signing up. The project also calls for Cognito, and keeping passwords out of the app fits the least-privilege goal of decision 0007.

## Decision

1. **Cognito's own pages** handle passwords, email codes and forgotten passwords. The app never sees a password.
2. **Authorization code flow with PKCE and no client secret.** The app checks the ID token's signature, issuer, audience, `token_use`, expiry and nonce, and that the address is verified. It keeps no tokens: its usual session cookie takes over.
3. **Cognito says who someone is; the portal says what they may do.** Approval, suspension and admin rights stay in the portal, and suspending someone still takes effect at once.
4. **A person is linked by Cognito's `sub`** at their first sign-in, matched by verified email. After that the `sub` decides, so changing an address at Cognito can't take over another record. A second Cognito user with a linked address is refused.
5. **The first admin** needs two settings with one email: a Cognito user, and `SEED_ADMIN_EMAIL`. The stack sets both from `AdminEmail`, and Cognito emails the temporary password, so no secret store holds it.
6. **The portal's password code stays,** used only when the `COGNITO_*` settings are unset: on a developer's machine, in tests, and in Lab 1 before Part 4. When they're set, its routes answer 404.

## Options considered

- **The app's own forms calling Cognito's API:** keeps a Thai page, but the app handles passwords again, which is what this decision removes.
- **A client secret:** adds a secret to protect and rotate. PKCE already makes a stolen code useless.
- **Admin rights in Cognito groups:** would split authority between two places, and every admin change would need the AWS console.
- **Moving existing password hashes to Cognito:** not needed. Each stack starts empty, and in Lab 1 the same email links to the existing record.

## Consequences

- Cognito's pages are in English, and only their logo and colours can be changed.
- Wrong passwords no longer appear in the portal's activity log, because they happen at Cognito.
- Cognito's built-in email allows 50 messages a day per account, enough for a class demo.
- Deleting the stack deletes the users along with the data.
