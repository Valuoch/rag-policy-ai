# SEC-001 Information Security Policy

| Field | Value |
|---|---|
| Document ID | SEC-001 |
| Title | Information Security Policy |
| Version | 3.2 |
| Effective date | 2026-01-01 |
| Owner | Chief Information Security Officer (CISO) |
| Applies to | All Lumora Systems, Inc. employees, contractors, interns, and temporary workers, and any third party with access to Lumora systems or data |
| Company | Lumora Systems, Inc. |
| Contact | security@lumora.example |

---

## 1. Purpose

Lumora Systems, Inc. ("Lumora") is a B2B analytics SaaS company. Our customers trust us with their business data, and that trust is the foundation of our business. This Information Security Policy sets out the minimum security requirements that every person working for or with Lumora must follow to protect the confidentiality, integrity, and availability of company and customer information.

This policy is the top-level security document at Lumora. It defines the rules for data classification, passwords, multi-factor authentication, device security, patching, access management, security training, and incident reporting. More detailed rules for day-to-day use of company technology are in SEC-002 IT Acceptable Use Policy, and rules for personal data are in LEG-001 Data Privacy & Protection Policy.

## 2. Scope

This policy applies to:

- All employees of Lumora, whether they work On-site, Hybrid, or Remote, in the Austin, Texas headquarters, the Raleigh, North Carolina office, or from home anywhere in the United States.
- Contractors, consultants, interns, and temporary workers who are given a Lumora account or access to Lumora data.
- All company-owned devices, including laptops, monitors, phones, and peripherals.
- Personal devices (such as personal phones) that are used to access company email, Slack, or other company systems.
- All company systems, cloud services, SaaS applications, networks, and data, wherever they are hosted.

Third-party vendors are bound by the security terms in their contracts, which must be at least as protective as this policy.

## 3. Roles and Responsibilities

### 3.1 Chief Information Security Officer (CISO)

The CISO owns this policy, approves exceptions, leads the Security team, and reports security risk to the executive team. The CISO reviews this policy at least once a year.

### 3.2 Security team

The Security team operates security tools, investigates incidents, runs the security awareness and phishing simulation program, approves security exceptions submitted through ServiceNow, and coordinates quarterly access reviews.

### 3.3 IT team

The IT team provisions and configures devices, enforces encryption and screen-lock settings, deploys patches, manages Microsoft Intune enrollment, and handles requests submitted through the "Lumora Help" ServiceNow portal or it-help@lumora.example.

### 3.4 Managers

Managers approve access requests for their team members, complete quarterly access reviews for the systems they own or for their direct reports, make sure their teams complete required training, and notify HR promptly about departures so access can be removed on time.

### 3.5 All workforce members

Everyone covered by this policy must protect the information they handle, follow this policy, complete required training, and report suspected security incidents immediately.

## 4. Definitions

- **Asset**: Any device, system, application, account, or piece of data owned or managed by Lumora.
- **Confidentiality**: Ensuring information is only available to people who are authorized to see it.
- **Integrity**: Ensuring information is accurate and has not been changed without authorization.
- **Availability**: Ensuring information and systems are accessible to authorized people when needed.
- **Security incident**: Any event that actually or potentially compromises the confidentiality, integrity, or availability of Lumora information or systems. Examples include a lost laptop, a clicked phishing link, malware, unauthorized access, or data sent to the wrong recipient.
- **MFA (multi-factor authentication)**: Signing in with something you know (a password) plus something you have (an Okta Verify push on an enrolled device, or a hardware security key).
- **Least privilege**: Granting a user only the minimum access needed to perform their job.
- **MDM / app protection**: Mobile device management and app protection policies enforced through Microsoft Intune.
- **EDR**: Endpoint detection and response software. Lumora uses CrowdStrike on all company laptops.
- **Restricted data**: The most sensitive data classification, defined in Section 5.

## 5. Data Classification

### 5.1 Classification levels

All Lumora information must be classified into one of four levels. When in doubt, choose the higher classification.

| Level | Description | Examples |
|---|---|---|
| Public | Information approved for release to the public. Disclosure causes no harm. | Marketing website content, published blog posts, press releases, public job postings |
| Internal | Information for use inside Lumora. Disclosure would cause minor harm. | Internal wiki pages, org charts, general Slack conversations, internal process documents |
| Confidential | Sensitive business information. Disclosure could cause significant harm to Lumora. | Product roadmaps, source code, contracts, pricing strategy, non-public vendor terms, security architecture |
| Restricted | The most sensitive information. Disclosure could cause severe harm to Lumora, customers, or individuals, or create legal liability. | Customer data, personally identifiable information (PII), credentials (passwords, API keys, tokens, private keys), financial results before public release |

### 5.2 Handling rules by classification

- **Public** data may be shared freely once it has been approved for release.
- **Internal** data may be shared with anyone at Lumora but must not be posted publicly or shared with outside parties without a business need.
- **Confidential** data may be shared only with people who have a business need to know. It may be shared externally only under a signed non-disclosure agreement or contract. It must be stored only in approved company systems.
- **Restricted** data must be accessed only by specifically authorized people, must be encrypted in transit and at rest, must never be sent by unencrypted email or posted in open Slack channels, must never be stored on personal devices or removable media, and must never be entered into unapproved or public AI tools (see SEC-002).

### 5.3 Labeling

Documents containing Confidential or Restricted data should be labeled with their classification in the header, footer, or file name. Unlabeled information is treated as Internal by default, unless its content makes it obviously Confidential or Restricted.

## 6. Passwords and Authentication

### 6.1 Password requirements

Passwords must be at least 14 characters long. Longer passphrases made of several unrelated words are encouraged because they are both strong and easy to type.

Additional password rules:

- Never reuse a password. Every work account must have a unique password, and work passwords must never be used for personal accounts.
- Never share a password with anyone, including your manager or IT staff. Lumora IT will never ask for your password.
- Never write passwords on paper, in plain-text files, in spreadsheets, or in Slack messages.
- Lumora does not require forced periodic password rotation. You must change a password immediately if compromise is suspected, for example after a phishing incident, a malware infection, or if the password may have been seen by someone else.

### 6.2 Password manager

All work passwords must be stored in 1Password, the company-provided password manager. Every employee receives a 1Password account during onboarding. Use the 1Password generator to create new passwords. Shared team credentials, where unavoidable, must be stored in a shared 1Password vault with access limited to the people who need it, never in documents or chat.

### 6.3 Multi-factor authentication

MFA is required for all company systems. Approved MFA methods are:

1. Okta Verify push notifications on an enrolled device.
2. Hardware security keys issued or approved by Lumora.

SMS (text message) codes are not allowed as an MFA method because they can be intercepted or redirected through SIM-swap attacks. Never approve an Okta Verify push that you did not initiate; deny it and report it to Security as a possible incident.

### 6.4 Lost MFA device

If you lose the phone or hardware key you use for MFA, report it within 1 hour as a security incident (see Section 11) and open a ServiceNow ticket so IT can reset your MFA enrollment after verifying your identity.

## 7. Device Security

### 7.1 Company laptops

All company laptops must meet the following requirements, which IT configures before shipping:

- **Full-disk encryption** is mandatory on all laptops: BitLocker on Windows and FileVault on macOS. Do not disable or suspend encryption.
- **Automatic screen lock** activates after 5 minutes of inactivity. You must also lock your screen manually whenever you step away from your device, even briefly (Windows: Windows key + L; macOS: Control + Command + Q).
- **EDR**: CrowdStrike must be installed and running at all times. Disabling or tampering with security tools is prohibited (see SEC-002).
- **Operating system and software updates** must be installed according to the patching timelines in Section 8.
- **USB mass storage is blocked by default.** If you have a business need to use a USB storage device, submit a ServiceNow ticket; an exception is granted only if approved by Security. Approved exceptions are time-limited and may be revoked.

### 7.2 Personal phones and devices

Personal phones may be used to access company email and Slack only if they are enrolled in Microsoft Intune (MDM) app protection. Intune app protection keeps company data inside managed apps, prevents copying company data into personal apps, and allows IT to wipe company data (not personal data) if the device is lost or you leave Lumora. Personal laptops and personal computers must not be used to access Confidential or Restricted data.

### 7.3 Physical security

- Never leave a laptop unattended in a car, a public place, or a hotel room outside of a safe where one is available.
- Use a privacy screen when working with Confidential or Restricted data in public spaces such as airports, trains, or coffee shops.
- Wear your badge in Lumora offices and do not allow people to follow you through secured doors (tailgating). Escort visitors at all times.
- Dispose of printed Confidential or Restricted documents in locked shredding bins.

### 7.4 Network security

When working anywhere other than a Lumora office network, you must connect through the company VPN (GlobalProtect). Public Wi-Fi may be used only with the VPN connected. Further detail is in HR-004 Remote & Hybrid Work Policy.

## 8. Vulnerability and Patch Management

Lumora remediates vulnerabilities on a timeline based on severity:

| Severity | Remediation deadline |
|---|---|
| Critical | Within 72 hours |
| High | Within 14 days |
| Medium and Low (all others) | Within 30 days |

The deadline is measured from the time a patch or fix becomes available or the vulnerability is identified by the Security team, whichever is later. For laptops, IT pushes patches automatically; you must restart your device when prompted and must not postpone critical updates beyond the deadline. Devices that are out of compliance may lose access to company systems until they are updated. System owners who cannot meet a deadline must request a documented exception from Security, including compensating controls and a target fix date.

## 9. Access Management

### 9.1 Least privilege

Access to systems and data is granted on the principle of least privilege. Users receive only the access needed for their current role. Administrative or privileged access must be requested separately, justified, and approved by the system owner and Security.

### 9.2 Requesting access

Access requests are submitted through the Lumora Help ServiceNow portal and must be approved by the requester's manager and, where applicable, the system owner. Do not ask colleagues to share their accounts; account sharing is prohibited.

### 9.3 Quarterly access reviews

Access reviews are performed quarterly. System owners and managers must confirm that each user's access is still appropriate and remove any access that is no longer needed. Security tracks completion and escalates overdue reviews.

### 9.4 Role changes

When an employee changes roles, access no longer needed for the new role must be removed, and new access must be requested through the normal process.

### 9.5 Access removal at termination

Access must be removed within 24 hours of termination. For involuntary terminations, access is removed immediately. HR notifies IT through Workday, and managers must ensure departures are entered in Workday promptly. Departing employees must return company equipment as described in HR-008 Onboarding & Offboarding Procedures.

## 10. Security Awareness Training

- New hires must complete security awareness training within 30 days of their start date.
- All workforce members must complete security awareness training annually.
- The Security team runs phishing simulations quarterly. Simulated phishing emails look like real attacks. If you recognize one, use the "Report Phishing" button in your email client. If you click a simulated link, you will be directed to a short refresher module; repeated clicks may require additional training with your manager informed.

Failure to complete required training on time may result in suspension of system access until training is completed.

## 11. Incident Reporting

### 11.1 Reporting deadline

You must report any suspected security incident within 1 hour of discovering it. You do not need to be certain that an incident has occurred; report suspicions. Early reporting limits damage.

### 11.2 How to report

Use any of these channels:

- Email: security@lumora.example
- Slack: #sec-incidents
- Security incident hotline: 1-512-555-0199 (use the hotline if you cannot access email or Slack, for example if your laptop was stolen)

### 11.3 What to report

Report at minimum:

- Lost or stolen laptops, phones, badges, or hardware security keys.
- Clicked links or opened attachments in a suspected phishing email, or credentials entered on a suspicious page.
- Unexpected MFA push requests that you did not initiate.
- Suspected malware, ransomware, or unusual device behavior.
- Data sent to the wrong recipient, or Confidential or Restricted data shared publicly.
- Suspected unauthorized access to an account or system.

### 11.4 What to include

When reporting, include your name, a description of what happened, when it happened, which devices, accounts, or data may be affected, and any actions you have already taken. Do not delete suspicious emails or files and do not attempt to investigate on your own; Security may need the evidence.

### 11.5 Personal data incidents

If an incident may involve personal data, Security will coordinate with the Privacy team. Personal data breaches must also be reported to the privacy team within 24 hours of discovery, as described in LEG-001 Data Privacy & Protection Policy. Reporting to Security within 1 hour satisfies the first step; Security will loop in privacy@lumora.example.

### 11.6 Non-retaliation

Lumora does not punish people for good-faith reporting of incidents, including reporting their own mistakes such as clicking a phishing link. Failing to report a known incident, however, is a policy violation.

## 12. Exceptions

Exceptions to this policy must be requested through a ServiceNow ticket, must include a business justification and compensating controls, and must be approved by Security (and by the CISO for exceptions involving Restricted data). Exceptions are time-limited and reviewed before renewal.

## 13. Enforcement

Violations of this policy may result in loss of system access and disciplinary action up to and including termination of employment or contract, consistent with HR-001 Employee Handbook & Code of Conduct. Illegal activity may be referred to law enforcement.

## 14. Frequently Asked Questions

### 14.1 How long does my password need to be?

At least 14 characters. Use 1Password to generate and store it.

### 14.2 Do I have to change my password every 90 days?

No. Lumora does not require forced periodic rotation. You must change a password only if you suspect it has been compromised.

### 14.3 Can I use SMS codes for MFA if I do not want Okta Verify on my phone?

No. SMS is not an allowed MFA method. If you do not want to use Okta Verify on a phone, request a hardware security key through ServiceNow.

### 14.4 I clicked a link in an email that now looks suspicious. What should I do?

Report it within 1 hour to security@lumora.example, in #sec-incidents, or by calling 1-512-555-0199. Do not delete the email. You will not be punished for reporting in good faith.

### 14.5 Can I copy files to a USB drive to give a presentation at a customer site?

USB mass storage is blocked by default. Submit a ServiceNow ticket explaining the business need; Security must approve the exception. Consider sharing the file through an approved cloud link instead.

### 14.6 Can I read my work email on my personal phone?

Yes, but only if your phone is enrolled in Microsoft Intune app protection. Instructions are available in the Lumora Help portal.

### 14.7 My laptop keeps asking me to restart for an update. Can I postpone it?

You may postpone briefly, but critical vulnerabilities must be patched within 72 hours. Devices that miss deadlines may be blocked from company systems.

### 14.8 Is customer data Confidential or Restricted?

Customer data is Restricted, the highest classification. The same applies to PII, credentials, and financial results before public release.

## 15. Related Policies

- SEC-002 IT Acceptable Use Policy
- LEG-001 Data Privacy & Protection Policy
- HR-001 Employee Handbook & Code of Conduct
- HR-004 Remote & Hybrid Work Policy
- HR-008 Onboarding & Offboarding Procedures
- FIN-002 Business Travel Policy

## 16. Revision History

| Version | Date | Author (role) | Summary of changes |
|---|---|---|---|
| 1.0 | 2019-03-01 | CISO | Initial policy. |
| 2.0 | 2021-06-15 | CISO | Added remote work device controls and VPN requirement. |
| 3.0 | 2024-01-01 | CISO | Removed forced periodic password rotation; raised minimum password length to 14 characters; disallowed SMS for MFA. |
| 3.1 | 2025-01-01 | CISO | Added Microsoft Intune app protection requirement for personal phones; clarified USB exception process. |
| 3.2 | 2026-01-01 | CISO | Clarified 1-hour incident reporting channels, coordination with Privacy team under LEG-001, and patching deadline measurement. |
