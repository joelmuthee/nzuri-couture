# Nzuri Couture — project rules for Claude (READ BEFORE EDITING)

New-stock women's-couture catalog. Global rules: `~/.claude/CLAUDE.md`. Catalog rules:
`Website Designs/CATALOG-STANDARDS.md`. **This file lists Nzuri-specific LOCKED decisions that
OVERRIDE the standard. Do not revert them across sessions without Joel's explicit say-so.**

## LOCKED DECISIONS — do NOT undo

1. **Enquire opens WhatsApp DIRECTLY via `wa.me` — NO Web Share API.**
   The owner rejected the OS "choose an app" picker that `navigator.share` triggers. `whatsappLink()`
   in `main.js` appends the worker `/p/<id>` OG share page so the product photo still previews in the
   WhatsApp message. **Do NOT add `navigator.share` / `navigator.canShare` / `tryShareWithImage`** — even
   though the global CATALOG-STANDARDS lists "Web Share (Tier 1)" as the default Enquire method, it is
   deliberately overridden here. (This has been reverted-in-by-mistake twice. Don't be the third.)

2. **WhatsApp number = `254794687724`** (0794 687 724). NOT `254717029815` (that is Bonnie's number, a
   copy-paste error). Lives in KV `settings.whatsappNumber` + hardcoded fallbacks in `main.js`.

3. **Live domain = `https://nzuricouture.co.ke`** (Truehost-registered, DNS on Cloudflare). OG/canonical/
   twitter (`index.html`), the worker `/p/<id>` `SITE` constant, and the admin broadcast link all point
   here. The temporary `nzuri-couture.essenceautomations.com` was removed — do NOT repoint to it.

4. **Data model = NEW-STOCK** (forked from `ryker-luxury`). Category set: Dresses, Tops, Skirts, Trousers,
   **Shorts**, Jumpsuits, Two-Piece Sets, Outerwear, Knitwear, Shoes, Bags, Accessories. Shorts is its own
   category (NOT Trousers) and "...set"/co-ord items route to Two-Piece Sets — both deliberate.

5. **Sale/markdown feature is live** (per-item `salePrice`, On-Sale pill, SALE ribbon, struck price, bulk
   Put-on-sale/Remove-sale). Don't strip it. New-stock tweak: do NOT delete `item.salePrice` on a unit sale.

6. **GHL buyer capture (`/api/buyer`) is intentionally DISABLED** — the template shipped Ryker's form/
   location IDs. Do NOT re-enable until a Nzuri GHL form exists (would file buyers into the wrong CRM).

7. **No "View on IG" button on cards** (removed per owner). The global standard ships one on IG-sourced
   catalogs, but the IG links aren't reliable for these items, so cards carry only the primary button.
   Do NOT re-add the `btn-card ig` / "View on IG" link in `main.js`.

8. **Button label = "Check availability" (NOT "Enquire").** Plain everyday language per the copy
   standard, matches buyer intent for new-stock (availability per size). Sold-out variant stays
   "Sold out · notify me". The WhatsApp message body matches: *"I'd like to check availability of
   *<Item>*…"* (not "I'd like to enquire about…"). Same for the wishlist drawer ("Check availability
   for all") and the How-to-buy step. Internal identifiers (`enquireBody`, `enquireImg`, the
   `.btn-card.primary` selector, the `enquire` GA event name) stay as-is — DO NOT rename them when
   updating the label, the visible text and the code symbols are intentionally decoupled.

## Infra (Stawisystems CF account `58685495706b973821d77208248c66fc`)
- Worker `nzuri-couture-api`; KV `nzuri-couture-bags` (id `b91f29983487476182b1acf14d28743b`); Pages
  project `nzuri-couture` (production branch `main`); repo `github.com/joelmuthee/nzuri-couture`
  (auto-deploys via GH Actions; needs repo secret `CLOUDFLARE_API_TOKEN`).
- IG seed/sync: `@nzuri.couture`, user_id `2097490880`; caption-based (`tools/seed_from_ig.py`).
- Admin password `nzuri123` (soft barrier; the real gate is the `ADMIN_TOKEN` CF worker secret).
- Google Analytics: GA4 `G-ZR9ZQHJLDZ` on the public site only (not admin).

## Deploy
Bump the relevant `?v=` query in `index.html`/`admin.html` on CSS/JS change, then push (GH Actions deploys)
or `wrangler pages deploy . --project-name=nzuri-couture --branch=main` + `wrangler deploy` in `worker/`.
