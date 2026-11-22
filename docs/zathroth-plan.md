# ZATHROTH plan

Agreed with the owner on 2026-11-22. Work through the steps in order; each
step starts only when the one before it is done and verified.

## 1. Open the server to the internet

Status (2026-11-22): host name `zathroth.servegame.com` is kept current by the
No-IP updater (systemd service `noip-duc` on the phone) and resolves to the
phone's public address. Verified from outside the home network on 2026-11-22:
TCP 8088, 7171 and 7172 connect and `http://zathroth.servegame.com:8088/health`
answers. The router forwards were correct from the start; the block was the
ThothOS Docker firewall, opened for these three ports with
`tools/thothos-open-ports.sh` (see `docs/zathroth.md`). Still to test: a real
client login and entering the game from outside.

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
  round trip). Done 2026-11-22: the owner's picture (`D:\ZATHROTH_edit\Zathroth_ Kingdoms
  Beneath Stormlight.png`, resized to 1920x1080 JPEG) is installed in
  `D:\ZATHROTH\bin\graphics_resources.rcc` (original in
  `D:\ZATHROTH_backup_original\bin\`), and `ZATHROTH-client.zip` (391 MB, without
  the `storeimages` cache) is in `downloads/` on the phone. The client has not
  been run on Windows by Claude.
- Store icons: the client loads them from `coinImagesURL` (`config.lua.dist`,
  now built from `ZATHROTH_SERVER_IP`) as
  `<base>/64/<name>.png` (products) and `<base>/13/<name>.png` (categories).
  The catalog uses OTClient-style names; CipSoft's host refuses outside
  downloads and the AAC packages in `D:\AAC` do not contain the icons. Done: generated placeholder tiles in `store-images/`, served by the account
  service; real icons with the same names replace them.

## 5. Client downloads in the browser account manager

Done: files in `downloads/` (zip, 7z, rar, exe, msi) are listed on the account
manager pages and served from `/downloads/<file>`; the client stays on the
phone, not on GitHub. `tools/package_client.py` makes the package.

- Add download links for the edited clients to the account manager pages.

## 6. Make the repository private again

Decision (2026-11-22): the owner chose to keep the repository public. Free
private repositories probably cannot use the arm64 runners that build the
phone's image, and `up.sh` downloads the image from the public release. Nothing
secret is in the repository (passwords live in ignored files; the client zip is
hosted on MediaFire, not in Git). Reopen only if that changes.

## 7. Store the edited clients

- Put the edited clients in the repository's GitHub Releases rather than in
  Git itself; client builds are large binaries and would bloat every clone.
