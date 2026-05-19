# Too Expensive Radar Commercial Site

This folder implements the first commercial model for the open-source radar: paid recurring opportunity reports.

## Business model

Start with a paid report, not a full SaaS paywall.

- `Single report`: $49 one-time report for demand validation.
- `Monthly brief`: $149/month recurring research product.
- `Custom research`: higher-ticket follow-up for agencies, affiliate operators, and SaaS studios.

The open-source engine creates the raw advantage: complaints, scores, replacement ideas, and affiliate paths. The paid product sells curation, ranking, proof links, and delivery cadence.

## Dodo Payments setup

Create products in the Dodo Payments dashboard, then set:

```bash
export DODO_PAYMENTS_API_KEY="..."
export DODO_REPORT_PRODUCT_ID="..."
export DODO_MONTHLY_PRODUCT_ID="..."
export DODO_PAYMENTS_ENV="test"
export COMMERCIAL_SITE_URL="http://localhost:8000"
```

The backend creates a hosted checkout session via `POST /checkouts` and redirects buyers to the returned `checkout_url`.

## Local route

Run the existing app and open:

```text
http://localhost:8000/commercial
```
