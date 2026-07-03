# CRM Schema - Canonical Definition

**Last updated:** 25/06/2026
**Used by:** JavaScript CRM (`@lozzalingo/crm`), Python CRM (`lozzalingo.modules.crm`)

This is the single source of truth for CRM table structures. Both frameworks must implement these tables identically. When adding or modifying fields, update this file FIRST, then implement in both frameworks.

## Column Naming Conventions
- JS (Prisma/MySQL): camelCase - `customerNumber`, `firstName`
- Python (SQLite): snake_case - `customer_number`, `first_name`
- API responses: camelCase JSON (both frameworks)

---

## Customer

The core contact record. Every person who interacts with any Lozzalingo site.

| Field | JS Name | Python Name | Type | Default | Notes |
|-------|---------|-------------|------|---------|-------|
| ID | id | id | UUID/string | auto | Primary key |
| Customer Number | customerNumber | customer_number | string | - | Unique, e.g. "#BR0001" |
| Fingerprint | fingerprint | fingerprint | string? | null | Links anonymous visitor data |
| First Name | firstName | first_name | string | - | Required |
| Last Name | lastName | last_name | string | - | Required |
| Email | email | email | string | - | Unique, required |
| Phone | phone | phone | string? | null | |
| Company | company | company | string? | null | |
| Job Title | jobTitle | job_title | string? | null | |
| Date of Birth | dateOfBirth | date_of_birth | datetime? | null | |
| Country | country | country | string? | null | |
| Region | region | region | string? | null | |
| Latitude | lat | lat | float? | null | |
| Longitude | lng | lng | float? | null | |
| IP Address | ipAddress | ip_address | string? | null | |
| Source | source | source | string? | null | First-touch origin |
| Status | status | status | enum | ACTIVE | ACTIVE, UNSUBSCRIBED, BOUNCED |
| Marketing Opt-in | marketingOptIn | marketing_opt_in | boolean | false | Double opt-in confirmed |
| Total Spent | totalSpent | total_spent | integer | 0 | In pence, cached |
| Total Bookings | totalBookings | total_bookings | integer | 0 | Cached count |
| Last Activity | lastActivityAt | last_activity_at | datetime? | null | Last engagement |
| Referral Name | referralName | referral_name | string? | null | |
| Referral Email | referralEmail | referral_email | string? | null | |
| LinkedIn URL | linkedinUrl | linkedin_url | string? | null | Full profile URL |
| Instagram Handle | instagramHandle | instagram_handle | string? | null | With or without @ |
| Website URL | websiteUrl | website_url | string? | null | |
| Notes | notes | notes | text? | null | |
| Terms Accepted | termsAcceptedAt | terms_accepted_at | datetime? | null | |
| Privacy Accepted | privacyAcceptedAt | privacy_accepted_at | datetime? | null | |
| Created At | createdAt | created_at | datetime | now() | |
| Updated At | updatedAt | updated_at | datetime | auto | |

**Indexes:** email, source, status, fingerprint, customerNumber

---

## CustomerActivity

Every interaction a customer has, whether they paid or not.

| Field | JS Name | Python Name | Type | Default | Notes |
|-------|---------|-------------|------|---------|-------|
| ID | id | id | UUID/string | auto | Primary key |
| Customer ID | customerId | customer_id | string | - | FK to Customer |
| Type | type | type | enum | - | See activity types below |
| Source | source | source | string? | null | "website", "etsy", "app" |
| Channel | channel | channel | string? | null | "Website Sign Up", "Etsy Store" |
| Product Ref | productRef | product_ref | string? | null | ID from site product table |
| Product Model | productModel | product_model | string? | null | "Event", "Product" |
| Product Name | productName | product_name | string? | null | Denormalised for display |
| Product Category | productCategory | product_category | string? | null | "Scavenger Hunt", "Quiz" |
| Platform | platform | platform | string? | null | "Virtual", "Real-World" |
| Group Type | groupType | group_type | string? | null | "Corporate", "Private" |
| Audience | audience | audience | string? | null | "Adult", "Children", "Mixed" |
| Location | location | location | string? | null | |
| Region | region | region | string? | null | |
| Country | country | country | string? | null | |
| Team Name | teamName | team_name | string? | null | |
| Event Date | eventDate | event_date | datetime? | null | |
| Metadata | metadata | metadata | text? | null | JSON string |
| Created At | createdAt | created_at | datetime | now() | |

**Activity Types:** GAME_PLAYED, PRODUCT_USED, WEBSITE_VISIT, APP_INTERACTION, FREE_CONTENT, ENQUIRY, SIGNUP

**Indexes:** customerId, type, createdAt

---

## CustomerScore

Marketing score per customer with category breakdown.

| Field | JS Name | Python Name | Type | Default | Notes |
|-------|---------|-------------|------|---------|-------|
| ID | id | id | UUID/string | auto | Primary key |
| Customer ID | customerId | customer_id | string | - | Unique FK to Customer |
| Score | score | score | integer | 0 | Total score |
| Breakdown | breakdown | breakdown | text | - | JSON object |
| Updated At | updatedAt | updated_at | datetime | auto | |

**Breakdown JSON format:** `{"profile": 25, "purchase": 40, "advocacy": 10, "engagement": 18, "decay": -10}`

**Index:** score

### Scoring Signals

| Signal | Points | Category |
|--------|--------|----------|
| Has email | +5 | Profile |
| Has phone | +5 | Profile |
| Has company (B2B lead) | +10 | Profile |
| Marketing double opt-in | +5 | Profile |
| Each completed booking | +20 | Purchase |
| Referred someone | +10 | Advocacy |
| Each email opened | +2 | Engagement |
| Each email clicked | +5 | Engagement |
| Each website visit | +1 | Engagement |
| Each product/game played | +10 | Engagement |
| Each app interaction | +5 | Engagement |
| Returning visitor (within 30 days) | +5 | Engagement |
| Inactive 3+ months | -5 | Decay |
| Inactive 6+ months | -10 | Decay |
| Inactive 12+ months | -15 | Decay |

---

## MarketingPreference

One row per product-line opt-in per customer.

| Field | JS Name | Python Name | Type | Default | Notes |
|-------|---------|-------------|------|---------|-------|
| ID | id | id | UUID/string | auto | Primary key |
| Customer ID | customerId | customer_id | string | - | FK to Customer |
| Preference | preference | preference | string | - | e.g. "Virtual Games" |
| Opted In | optedIn | opted_in | boolean | true | |
| Updated At | updatedAt | updated_at | datetime | auto | |

**Unique constraint:** (customerId, preference)

---

## Campaign

Email campaign records.

| Field | JS Name | Python Name | Type | Default | Notes |
|-------|---------|-------------|------|---------|-------|
| ID | id | id | UUID/string | auto | Primary key |
| Name | name | name | string | - | Required |
| Subject | subject | subject | string | - | Required |
| Sent At | sentAt | sent_at | datetime? | null | |
| Total Sent | totalSent | total_sent | integer | 0 | |
| Total Opened | totalOpened | total_opened | integer | 0 | |
| Total Clicked | totalClicked | total_clicked | integer | 0 | |
| Created At | createdAt | created_at | datetime | now() | |

---

## CampaignSend

Individual send record per customer per campaign.

| Field | JS Name | Python Name | Type | Default | Notes |
|-------|---------|-------------|------|---------|-------|
| ID | id | id | UUID/string | auto | Primary key |
| Campaign ID | campaignId | campaign_id | string | - | FK to Campaign |
| Customer ID | customerId | customer_id | string | - | FK to Customer |
| Sent At | sentAt | sent_at | datetime | now() | |
| Opened | opened | opened | boolean | false | |
| Opened At | openedAt | opened_at | datetime? | null | |
| Clicked | clicked | clicked | boolean | false | |
| Clicked At | clickedAt | clicked_at | datetime? | null | |

**Indexes:** campaignId, customerId, sentAt

**Note:** FBQ uses `CrmCampaign`/`CrmCampaignSend` model names to avoid clash with an existing Campaign model. The table structure is identical.

---

## SubscriberConfirmation

Double opt-in confirmation tokens. Sets `customer.marketingOptIn = true` on confirmation.

| Field | JS Name | Python Name | Type | Default | Notes |
|-------|---------|-------------|------|---------|-------|
| ID | id | id | UUID/string | auto | Primary key |
| Customer ID | customerId | customer_id | string | - | FK to Customer |
| Token | token | token | string | - | Unique |
| Expires At | expiresAt | expires_at | datetime | - | Required |
| Confirmed | confirmed | confirmed | boolean | false | |
| Created At | createdAt | created_at | datetime | now() | |

**Index:** customerId

---

## Change Log

| Date | Change | Added By |
|------|--------|----------|
| 25/06/2026 | Initial schema definition | JS CRM agent |
| 25/06/2026 | Added linkedinUrl, instagramHandle, websiteUrl to Customer | JS CRM agent |
