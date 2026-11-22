# ZATHROTH plan

Agreed with the owner on 2026-11-22. Work through the steps in order; each
step starts only when the one before it is done and verified.

## 1. Open the server to the internet

Status (2026-11-22): host name `zathroth.servegame.com` is kept current by the
No-IP updater (systemd service `noip-duc` on the phone) and resolves to the
phone's public address. The phone's `.env` sets `ZATHROTH_SERVER_IP` to the
host name and `ZATHROTH_LAN_IP` to the LAN address (home-network clients get
the LAN address, everyone else the host name). Still to verify from outside
the home network: ports 8088, 7171 and 7172 (open `http://zathroth.servegame.com:8088/`
on mobile data, then log in with the client).

HTTPS decision: skipped for now. Let's Encrypt could not reach ports 80 or 443
from the internet (both answer on the home network), and the game client logs
in over plain HTTP on 8088 anyway, so HTTPS would only protect the website.
The Caddy `https` compose profile stays in the repo, off by default; the
owner may remove the 80 and 443 forwards from the router.

- Router: forward TCP 7171, 7172 and 8088 to the phone (`192.168.1.104`) and
  reserve that address for the phone in the router's DHCP settings.
- No-IP hostname kept current by the No-IP updater (on the router or another
  always-on device).
- On the phone, `.env` in the clone: `ZATHROTH_SERVER_IP=<no-ip hostname>` and
  `ZATHROTH_BIND_IP=192.168.1.104`, then `docker compose up -d`.
- Check for CGNAT first: the router's WAN address must match the address No-IP
  reports. If it does not, port forwarding cannot work and a tunnel or a
  public IP from the ISP is needed.
- Verify from outside the home network (mobile data): login on 8088, character
  list, entering the game on 7172.

## 2. Security review of the browser account manager, and a CAPTCHA

Status: done. HTTPS is built (Caddy `https` compose profile) but stays off until the No-IP host name exists; to switch it on, see the README. Done:
self-hosted CAPTCHA on registration and after 3 failed sign-ins; failed-login
blocking per address and per account, also for the game client's login;
caps on new accounts per address and per hour (browser and in game);
connection caps and a 30 second connection deadline; common-password check;
unit tests in CI; HTTPS through Caddy with the real visitor address and a
`Secure` cookie. Not done: password recovery (there is none; the email is not
verified, a lost password needs a god to reset it).

- Review `account_manager/` as internet-facing code: login and registration,
  sessions and CSRF, rate limiting and lockout on failed logins, password
  rules, input validation, error messages, HTTP headers.
- Decide whether to serve it over HTTPS (for example a reverse proxy with a
  certificate for the No-IP hostname); passwords currently travel as plain
  HTTP.
- Add a CAPTCHA to registration (and to sign-in after failed attempts).
  Prefer a self-hosted CAPTCHA so the server keeps working without a third
  party; an external service (hCaptcha, Cloudflare Turnstile) needs keys and
  an internet call per check.
- Decide what the shared 1/1 login may do once the server is public.

## 3. Trim the phone

Done 2026-11-22: all other containers were stopped with restart policy "no"
(monerostage-wallet-1, infura-explorer-explorer-1, stagenet_monerod_explorer,
tonapi-explorer-1, tonapi-api-1, monerostage-explorer-1,
stagenet_monerod_prometheus, stagenet_monerod_nodemapper,
stagenet_monerod_exporter, stagenet_monerod, stagenet_monerod_tor,
stagenet_monerod_i2p, stagenet_monerod_grafana; epic-server-linux-epic-1 was
already stopped). Only Portainer and the two ZATHROTH containers run. Start
one again with `docker start <name>`. The phone's "load average 18" is a kernel
artifact (permanently waiting thermal worker threads), not real load.

- Stop every container on ThothOS except Portainer and the two ZATHROTH
  containers (`game`, `accounts`), and stop them from restarting on boot.
- List the containers and their restart policies before stopping anything,
  and confirm the list with the owner.

## 4. Client

Decision (2026-11-22): no OTClient v8. We keep the normal client already in
use (OTClient Redemption with 15.25 assets, `httpLogin`).

- Edit the client's login background picture with ZATHROTH artwork.
- Rebrand it (window title, logo, server list entry with the login URL
  `http://zathroth.servegame.com:8088/login`, protocol 1525) and check its
  licence allows redistribution.
- The client is the official 15.25 client in `D:\ZATHROTH` (from
  dudantas/tibia-client). Done: `conf/config.ini` has the login address
  `http://zathroth.servegame.com:8088/login.php`, every tibia.com, YouTube,
  Twitch and CipSoft link now points at the account manager or at a closed local
  port; the original is in `D:\ZATHROTH_backup_original\conf\config.ini`.
- The login background is `/images/title.jpg` (1920x1080 JPEG) inside
  `bin/graphics_resources.rcc`; a copy to edit is `D:\ZATHROTH_edit\title.jpg`.
  `tools/rcc_replace.py` puts the edited picture back (verified byte-identical
  round trip). Waiting for the owner's picture, then package the client into
  `downloads/` on the phone. The client has not been run on Windows by Claude.

## 5. Client downloads in the browser account manager

Done: files in `downloads/` (zip, 7z, rar, exe, msi) are listed on the account
manager pages and served from `/downloads/<file>`; the client stays on the
phone, not on GitHub. `tools/package_client.py` makes the package.

- Add download links for the edited clients to the account manager pages.

## 6. Make the repository private again

Open question (2026-11-22): the GitHub account is on the Free plan. Free
private repositories get 2,000 Actions minutes a month, and the arm64 build
(`ubuntu-24.04-arm`, which makes the phone's image) is probably not available
to private repositories on the Free plan. Not done until the owner decides.

- Before switching, decide how the phone keeps receiving images: `up.sh`
  downloads the image from the public GitHub release, which stops working
  for anonymous downloads once the repository is private. Options: a
  read-only token on the phone for ghcr.io or the release, or another image
  host.
- Canary is GPL-2.0: anyone who receives the server program can ask for its
  source.

## 7. Store the edited clients

- Put the edited clients in the repository's GitHub Releases rather than in
  Git itself; client builds are large binaries and would bloat every clone.
