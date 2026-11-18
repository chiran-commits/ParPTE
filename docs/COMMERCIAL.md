# Running ParPTE as a subscription business

## Plans and access

Plans live in `backend/app/config.py → PLANS`: name, price, daily AI-scoring quota and allowed mock types. Objective Reading and Listening questions never use quota. Admin accounts (`ADMIN_EMAILS`) always get Premium for free. Admins can change any user's plan and expiry from **Admin → Users**.

## Payments

`POST /api/billing/checkout` (in `routes/admin.py`) is the hook. A typical integration:

1. Create a checkout session with your provider and return `{"url": ...}`. The frontend already redirects to it.
2. Add a webhook route that verifies the provider's signature, then sets `user.plan` and `user.plan_expires_at`.
3. Set `BILLING_PROVIDER` in the environment.

Options:

* **PayHere**: Sri Lankan gateway that accepts local and international cards, with recurring payments.
* **Paddle** or **Lemon Squeezy**: merchant-of-record services that handle international sales tax and VAT for you. Simplest for selling worldwide.
* **Stripe**: check whether it supports merchants in your country before relying on it.

## Content and intellectual property

* The bundled question bank is **original**. Don't import questions copied from Pearson's official materials or from other prep platforms. That content is copyrighted, and "real exam questions" collections often come from leaked tests, which breaches Pearson's terms.
* Don't use Pearson's logos, or anything implying you're endorsed by Pearson. The footer disclaimer is already in place.
* **Training data licences:** speechocean762 is CC BY 4.0 (commercial use allowed with attribution; add a credit on an About page). Check the licence of the Feedback Prize ELL / ELLIPSE data on Kaggle before using the essay model for paying users. If it's non-commercial, ship the rule-based writing scorer to customers.
* Browser speech recognition in Chrome sends audio to Google. With Whisper installed on your server, transcription stays on your own infrastructure. Mention whichever applies in your privacy policy.

## Before launch

* Set a strong `SECRET_KEY` and use Postgres (`docker-compose.yml` does both).
* Serve over HTTPS. Browsers only allow microphone access on HTTPS or localhost.
* Write a privacy policy (voice recordings are personal data; recordings are scored in memory and not stored by default) and terms of service.
* Replace browser TTS with recorded or neural audio files (`audio_url` on any question) for consistent, high-quality listening prompts.
* Calibrate the score curve once you have real results (`docs/SCORING.md`).
