# ZATHROTH plan

Agreed with the owner on 2026-11-22. Work through the steps in order; each
step starts only when the one before it is done and verified.

## 1. Open the server to the internet

Status (2026-11-22): host name `zathroth.servegame.com` is kept current by the
No-IP updater (systemd service `noip-duc` on the phone) and resolves to the
phone's public address. The phone's `.env` sets the host name, the HTTPS
profile and Let's Encrypt's staging CA. Let's Encrypt could not reach ports 80
or 443 from the internet ("Timeout during connect"), while both answer on the
home network. Open: find out whether the router forwards are active, the
router's WAN address equals the public address the phone sees (CGNAT), or the
ISP blocks inbound 80/443; test 8088 from mobile data. When 80/443 are
reachable, Caddy gets the staging certificate by itself; then remove
`ZATHROTH_ACME_CA` from `.env` and run `docker compose up -d` for the real one.

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

- Stop every container on ThothOS except Portainer and the two ZATHROTH
  containers (`game`, `accounts`), and stop them from restarting on boot.
- List the containers and their restart policies before stopping anything,
  and confirm the list with the owner.

## 4. Client

- Edit the client's login background picture with ZATHROTH artwork.
- The owner collects OTClient v8 builds from other servers; test which one
  works with ZATHROTH (protocol 15.25 over HTTP login). Players prefer OTClient
  v8 because of its built-in bot.
- Rebrand the chosen client (name, logo, server list entry, login URL) and
  check its licence allows redistribution.

## 5. Client downloads in the browser account manager

- Add download links for the edited clients to the account manager pages.

## 6. Make the repository private again

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
