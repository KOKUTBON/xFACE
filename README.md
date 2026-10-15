# xFACE

A face recognition access-control app for managing people, monitoring an entrance, and reviewing access logs.

[Open the demo](https://kokutbon.github.io/xFACE/) · [Technical documentation](docs/)

## Features

- Manage enrolled people from a web dashboard.
- View recognition events and access decisions.
- Connect optional cameras, CompreFace, and door relays.

## Screenshots

![xFACE main workspace](docs/screenshots/dashboard.png)

![xFACE detail view](docs/screenshots/live-monitor.png)

## Technology

Python 3.10+, Flask, OpenCV, SQLAlchemy; optional CompreFace and Shelly integrations.

## Run the demo locally

```sh
git clone https://github.com/KOKUTBON/xFACE.git
cd xFACE
python3 -m http.server 8000 --directory site
```

Open http://localhost:8000/. The browser demo uses sample data. See the technical documentation for the full application setup.

## License

[MIT License](LICENSE).
