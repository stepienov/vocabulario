# Vocabulario Privacy Policy

**Status:** draft for legal review (23.11.2026), not published. **Version:** [TO CONFIRM: new identifier; do not reuse `2026-06-01`]. **Effective date:** [TO CONFIRM].

This policy explains how we process your personal data when you use the Vocabulario Android app, the vocabulario.io website and our support channels. It is information, not a contract you have to accept. The Spanish version is the reference text.

## 1. Controller

{operator}, the developer of Vocabulario on Google Play. [TO CONFIRM: operator details and legal form.]

Tax ID (NIF): {nif} · Address: {address} · E-mail: {contact} · Phone: {phone}.

We are not required to appoint a data protection officer. For any privacy matter, write to {contact}.

## 2. Data, purposes and legal bases

| Data | Purpose | Legal basis (GDPR) |
|---|---|---|
| **Account:** e-mail address; a cryptographic hash of your password, or your Google account identifier and the e-mail address Google gives us; date the e-mail address was verified; settings; accepted version of the Terms, separate acknowledgement of receipt of privacy information and confirmation that you are an adult, with their dates | Create and keep the account, sign in, recover access and prove acceptance of the Terms and delivery of information | Performance of the contract (Art. 6(1)(b)); proof of acceptance and delivery, legitimate interest (Art. 6(1)(f)) |
| **Learning:** language and level profiles, words and phrases you look up, cards, lists, progress and review grades, imports (pasted text, files or public Quizlet/AnkiWeb links), correction requests and card history | Provide the service and sync your devices | Performance of the contract |
| **AI generation:** the text needed for each request, including the full card and the note/selection you attach to a correction request. Text may contain personal data you have included. We do not automatically add your account e-mail address or name to the request | Generate meanings, examples, exercises and assess corrections | Performance of the contract |
| **Correction evidence:** the lemma and selected terms or glosses from a card are looked up in Wiktionary as evidence for automatically assessing a reported correction. We do not automatically add your account e-mail address or identifier; text you enter may contain them | Check the requested correction | Performance of the contract |
| **Shared search cache:** queries and results may be reused to handle the same lookup for other users and may contain personal data | Speed up and provide the lookup feature | [TO CONFIRM: determine the legal basis, purpose compatibility and safeguards; do not publish until resolved] |
| **Security:** session identifiers (we keep only a hash of the token) and their dates; a cryptographic pseudonym (HMAC) of the IP address or e-mail address to limit sign-in attempts; a pseudonymised record of security and account deletion events | Protect accounts and the service and prevent abuse. Handling deleted data after a backup restoration remains to be verified | Legitimate interest in security (Art. 6(1)(f)) and the duty of security (Art. 32) |
| **Technical and cost logs:** request type, route without identifiers, result, duration, error type and account or profile identifiers; AI metrics (model, tokens, estimated cost) without the request text | Stability, error diagnosis and control of AI spending | Legitimate interest |
| **Transactional e-mail:** address, content (verification, reset or deletion links) and delivery status | Send the messages the account needs | Performance of the contract |
| **Reports and support:** reported excerpt, reason, note, app version and messages you send us | Review content, answer questions and handle rights requests | Performance of the contract, legitimate interest and, for notices of illegal content, legal obligation (Art. 6(1)(c); Regulation (EU) 2022/2065) |

We do not use your data for advertising, do not sell it, do not build commercial profiles and do not take automated decisions with legal or similarly significant effects (Art. 22 GDPR). When you ask us to correct a card, an automated AI assessment only decides whether that card is changed.

We need an e-mail address or a Google account to create the account; without them we cannot provide the service. You can object to processing based on legitimate interest (section 10).

## 3. Source of the data

The data comes from you, from the app (for example, its version) and, if you choose to sign in with Google, from Google (account identifier and e-mail address).

## 4. Data on your device

The app keeps your learning data, settings and the (encrypted) session in its private storage so that it works offline. This data is excluded from Android backups and device-to-device transfer. Uninstalling the app erases it from the device but **does not delete your account**. If you sign out while offline, the app keeps an encrypted item to revoke the session once the connection returns.

Study reminders are local notifications; we do not use push notifications. Pronunciation uses your device's text-to-speech engine; depending on its settings, the provider of that engine may process the text read aloud. The app contains no advertising or analytics kits and does not use the advertising ID.

## 5. The vocabulario.io website and cookies

The vocabulario.io pages use no cookies, analytics or trackers. On the account deletion page, only if you choose to continue with Google, Google's sign-in service loads and may use its own cookies to provide the service you request. Your browser temporarily keeps the status of your request (session storage). These technologies are strictly necessary (Art. 22(2) of the Spanish LSSI). The tenedevia.com website has its own privacy and cookie policy.

## 6. Recipients

| Recipient | Role |
|---|---|
| Railway | The production server and database are in Amsterdam, the Netherlands, according to information provided by the controller. Locations of manual backups and all Railway services need separate confirmation. Processor |
| OpenAI | AI content generation and assessment of corrections. Processor; the terms, region and retention period for the specific account need confirmation |
| Resend | Sending account e-mails. Processor; the region and terms for the specific account need confirmation |
| [TO CONFIRM: provider of the {contact} mailbox] | Support mailbox. Processor |
| Google | Only if you sign in with Google: it processes your Google account data as an independent controller under its own policy |
| Wikimedia Foundation | When assessing a reported correction, our server may send the lemma and selected terms or glosses taken from the card. Wiktionary is not a source for ordinary word lookups. We have not confirmed that Wiktionary content is directly displayed in the app. Its legal role, API terms and licence/attribution requirements need confirmation |
| Quizlet or AnkiWeb | Only if you import from a link: our server downloads the public set you indicate |
| Authorities and advisers | When the law requires it or it is necessary to defend rights, under a duty of confidentiality |

Cards and account content are not shared with other users as content in their accounts. However, the shared search cache may contain queries and results, including personal data, and a cached result may be served to another user making the same lookup for the same language pair. It is not anonymous. Do not enter personal or confidential data in the lookup field.

## 7. International transfers

The Railway server and database used in production are in Amsterdam, the Netherlands, according to information provided by the controller. This does not mean that every provider, subprocessor or backup is in the EEA. OpenAI, Resend, Google, Wikimedia and the mailbox provider may process data outside the EEA. Before publication, the contracting entity, actual region and applicable transfer mechanism for each service must be confirmed. We do not claim that a particular provider is certified under the EU-US Data Privacy Framework or that particular standard contractual clauses apply without checking the relevant agreement and configuration. You can request information about safeguards at {contact}.

## 8. Retention periods

| Data | Period |
|---|---|
| Account, cards and progress | As long as you keep the account. We do not delete accounts for inactivity. The deletion process allows 7 days to cancel a request and aims to erase active data within 14 days of the request. A failure may delay the purge; this period cannot be guaranteed in every circumstance. The legal deadline for responding to a data-rights request is separate |
| Deleted cards and lists and sync tombstones | Temporarily retained to sync devices; the exact period and fields need verification before publication |
| Search history (including the query) | The target is to delete each event after 30 days. This mechanism has not been deployed and verified in production; until then the period may be longer |
| Results and the "Show more" operation query | A technical record stores the query and results without an automatic expiry; it is deleted when the account is deleted. No deadline has been set for adding automatic cleanup |
| Raw import data | Target after deployment: 30 days after a job completes, fails or is cancelled. Active jobs are not cleaned. Statuses, results, queue links and words saved to cards may remain |
| Shared search cache | Target after deployment: 90 days after its last use or change. It is shared and may contain personal data from a query; it is not anonymous. Failures or a backlog may delay cleanup |
| Application logs | 7 days by default; production configuration and Railway logs must be confirmed separately |
| AI usage metrics | 30 days by default; production configuration must be confirmed |
| Full copies of AI requests and responses | Diagnostic storage must be disabled for real data; confirm the production setting. Providers apply their own periods |
| E-mail content in our queue (encrypted) | After reaching a terminal state, no earlier than 24 hours after the message was created, during periodic cleanup; the queue record after 7 days from expiry, and provider events after 7 days from receipt. This is not the e-mail provider's period |
| Content reports | Up to 30 days after they are resolved; the minimal proof of submission (without content), while the account exists |
| Support messages | [TO BE SET before publication] |
| Security event record | 45 days; events related to an ongoing account-deletion process may be kept longer |
| Pseudonymised account-deletion process record | No final retention period has been set; it may remain after account deletion. The period and deletion rule must be set before publication |
| Backups | Railway automatic daily backups have 6 days' retention. A manual Railway backup exists with no confirmed expiry, as does a protected local logical backup with no confirmed expiry. The location of older backups is unconfirmed. We do not claim that all backups disappear within 30 days; duration, location and deletion procedure remain to be set |
| Railway logs | Actual period and region need confirmation; the TTL for our database logs does not determine Railway retention |
| External providers | Each provider has its own period and region. Confirm the effective terms of OpenAI, Resend, Google and the mailbox provider before publication |
| Dictionary entries and search cache | Some entries and results are shared between users. The cache may contain personal data and is not anonymous. Apply the periods above; retention of Wiktionary evidence depends on the provider |

## 9. Security

We use encrypted connections (HTTPS), store passwords and tokens only as cryptographic hashes, encrypt secrets and the e-mail queue, keep logs limited to technical data, and only the controller can access the administration console. No system is infallible; if we detect a personal data breach likely to result in a high risk to you, we will tell you.

## 10. Your rights

You can request access to, rectification, erasure, restriction of processing and portability of your data, and you can object to processing based on legitimate interest. Write to {contact} from your account's e-mail address or tell us how we can check your identity; we do not ask for copies of documents unless strictly necessary. We will reply within one month, which may be extended by two further months for complex requests, with prior notice.

You can delete the account in the app (Settings) or at https://vocabulario.io/delete-account; that process allows 7 days to cancel the request. If you specifically want to exercise your GDPR right to erasure, write to {contact}; we handle that request under the statutory time limits, and it is not automatically subject to the product's cancellation window. Accepting the Terms and acknowledging receipt of this policy are not consent to process personal data. If an optional feature relies on your consent, we will ask for it separately and you can withdraw it.

If you think we have not handled your rights properly, you can complain to the Spanish Data Protection Agency (https://www.aepd.es) or to the authority of your country of residence (in Poland, UODO: https://uodo.gov.pl).

## 11. Use of artificial intelligence

Vocabulario uses AI models to generate learning materials and assess requested corrections. Before using these features, you can check in this policy and the in-app notice what data is sent to each provider. Text you enter—including notes and imports—may contain personal data; do not enter other people's personal data or confidential information. Generated content may be wrong. The AI features are not intended to publish texts on matters of public interest or generate deepfakes or synthetic media. Pronunciation uses your device's text-to-speech engine, as described above; it is not an AI media-generation feature. The app is not an open-ended conversational AI assistant.

## 12. Age

Vocabulario is only for people aged 18 or over. If we learn that an account belongs to a minor, we will delete it.

## 13. Changes

We will publish each version with its date and notify you in the app or by e-mail before relevant changes take effect. We will retain previous versions and be able to identify which version was shown during registration.
