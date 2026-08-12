# Curator Web Access and Device Registration

> Applies to: Administrator, Writer, and Reader · Last verified: 2026-08-12

<!-- manual-section: concepts -->
## 1. Credential distinctions

Curator uses approved browser/device Tokens rather than usernames and passwords. A Bootstrap Code initializes only the first Administrator. A Registration Proof lets a browser submit a Reader/Writer request but grants no access. A Device Token is generated and retained by the requesting browser; the Backend stores only its hash and activates it after approval.

<!-- manual-section: bootstrap -->
## 2. Initialize the first Administrator

On the Backend host run:

```bash
python3 -m apps.backend auth create-bootstrap-code
```

Within ten minutes choose **Initialize administrator**, enter the Code and device name, then securely store the Admin Token shown once. Bootstrap is not an ordinary registration or recovery path.

<!-- manual-section: proof -->
## 3. Generate Registration Proof

Required role: Administrator. Open **Administrator Center → Devices and Tokens → Registration access** and choose **Generate Registration Proof**. Copy the value shown once into a trusted password manager. Rotation invalidates the previous Proof; disabling blocks new requests. Neither action changes approved Tokens.

<!-- manual-section: request -->
## 4. Request Reader or Writer access

In the new browser profile:

1. Open **Connect → Request device access**.
2. Enter a recognizable device name, select Reader or Writer, and enter the Registration Proof.
3. Choose **Request access**. The browser generates and safely retains its candidate Device Token and enrollment capability locally.
4. Leave the request Pending or close the window and return later in the same browser profile.

No terminal, developer console, UUID copying, JSON, or `curl` is required.

<!-- manual-section: approval -->
## 5. Approve or reject

Required role: Administrator. In **Pending registrations**, verify the full device identity, role, and scopes. Approve least privilege or reject the request. For UI enrollment, no Device Token is displayed in the Admin browser; approval activates the hash already submitted by the requesting browser.

<!-- manual-section: connection -->
## 6. Complete connection

Return to the requesting browser and choose **Check status**. Approval validates the locally held Token and connects automatically. Rejection or expiry never activates it. Do not clear site storage or switch browser profiles while enrollment is pending.

<!-- manual-section: lifecycle -->
## 7. Renewal, revocation, and loss

Request renewal from the original browser before expiry. Revoke a lost or exposed device immediately in **Devices and Tokens**. Existing Token plaintext cannot be recovered. **Disconnect** clears the browser connection but does not revoke the server Token.

<!-- manual-section: troubleshooting -->
## 8. Troubleshooting

- Invalid Proof: confirm the active value; Admin may have rotated or disabled it.
- Request not visible: refresh **Devices and Tokens** and confirm the requester reported Pending.
- Wrong browser: return to the exact profile that submitted the request.
- `401`: Token is invalid, expired, revoked, replaced, or not yet approved.
- `403`: current role/scopes do not permit the action.

<!-- manual-section: checklist -->
## 9. Verification checklist

- [ ] Proof and Tokens are absent from screenshots, logs, chats, and documents.
- [ ] The requesting browser profile remains unchanged through approval.
- [ ] Admin approved the full identity and least role/scopes.
- [ ] The requester connected automatically with the expected role.
