# Idegis / AstralPool cloud capturer

Home Assistant add-on for Idegis / AstralPool pool chlorinators.

See [DOCS.md](DOCS.md) for full documentation.

## Install

1. In Home Assistant: **Settings → Add-ons → ⋮ → Repositories** and add
   `https://github.com/hirofairlane/ha-idegis-astralpool`.
2. Install the **Idegis / AstralPool cloud capturer** add-on.
3. Install the companion `idegis_astralpool` integration in HACS (custom
   repository).
4. Add a DNS override on your LAN router that points `api.idegis.net` to
   the IP of your Home Assistant host.
5. Start the add-on. Configure the integration to talk to the add-on
   (host = your HA host, port = 8765).

## License

MIT (code) / CC-BY-SA 4.0 (docs). See the repository root.
