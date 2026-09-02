# Rock Lens

Rock Lens is a read-only Omarchy 4.0.2+ launcher for Rock RMS discovery. The
first slice runs entirely against public-safe mock data. QML is only a view:
search terms travel over an owner-only local Unix socket to a Python broker,
and only allowlisted display fields return.

![Rock Lens mock launcher](outputs/rock-lens-mvp.png)

## Run the MVP

```bash
python3 -m unittest discover -s tests -v
python3 -m rock_lens_broker --socket /tmp/rock-lens-demo.sock
```

The installed Omarchy integration uses `$XDG_RUNTIME_DIR/rock-lens/broker.sock`
and starts the broker without passing queries or credentials as arguments.
Summon it with `Super+R` or click the explicit `DEV` / `PROD` bar indicator.

## Safety guarantees

- Context is stored explicitly as `DEV` or `PROD`; it is never inferred from a
  path, host name, URL, or response.
- The mock adapter is the only enabled data adapter in this slice.
- Live adapters are capability-detected and fail closed.
- There is no mutation transport, SQL execution, job trigger, or Run Now UI.
- Broker errors are reduced to stable public codes. Response bodies, tokens,
  cookies, SQL, PII, and exceptions are not logged or forwarded to QML.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/VERIFICATION.md](docs/VERIFICATION.md).
